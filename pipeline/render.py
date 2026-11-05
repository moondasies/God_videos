"""Render an episode: audio -> per-shot video segments (parallel, cached) -> final MP4."""
from __future__ import annotations

import hashlib
import json
import os
import shutil
import subprocess
import time
from concurrent.futures import ProcessPoolExecutor
from pathlib import Path

import numpy as np
import soundfile as sf

from audio.dsp import SR
from audio.mix import mix
from voice.generate_dialogue import assemble_track

from .episode import ROOT, resolve_timeline, save_json

PRESETS = {
    "final": dict(w=1080, h=1920, fps=30, crf=18, x264="medium"),
    "preview": dict(w=540, h=960, fps=24, crf=24, x264="veryfast"),
}


def _code_hash():
    h = hashlib.sha1()
    for d in ("animation",):
        for f in sorted((ROOT / d).glob("*.py")):
            h.update(f.read_bytes())
    return h.hexdigest()[:12]


def shot_key(tl, i, preset):
    sh = tl["shots"][i]
    deps = {"shot": {k: v for k, v in sh.items() if k not in ("wav",)}, "preset": preset,
            "chars": tl.get("characters"), "code": _code_hash()}
    if sh.get("transition_in") in ("dissolve", "glow") and i > 0:
        deps["prev"] = tl["shots"][i - 1]
    if sh["start"] < 3.5:
        deps["title"] = (tl.get("title_roman"), tl.get("number"))
    if sh.get("type") == "moral":
        deps["moral"] = tl.get("moral")
    deps["subs"] = tl.get("subtitles")
    return hashlib.sha1(json.dumps(deps, sort_keys=True, default=str, ensure_ascii=False).encode()).hexdigest()[:16]


def _render_segment(args):
    tl, i, preset, out_path = args
    from animation.scene import EpisodeRenderer
    p = PRESETS[preset]
    R = EpisodeRenderer(tl, p["w"], p["h"])
    sh = tl["shots"][i]
    fps = p["fps"]
    f0 = round(sh["start"] * fps)
    f1 = round((sh["start"] + sh["duration"]) * fps)
    tmp = str(out_path) + ".tmp.mp4"
    cmd = ["ffmpeg", "-y", "-loglevel", "error", "-f", "rawvideo", "-pix_fmt", "rgba", "-s", f"{p['w']}x{p['h']}",
           "-r", str(fps), "-i", "-", "-c:v", "libx264", "-preset", p["x264"], "-crf", str(p["crf"]),
           "-pix_fmt", "yuv420p", "-profile:v", "high", "-r", str(fps), tmp]
    proc = subprocess.Popen(cmd, stdin=subprocess.PIPE)
    t0 = time.time()
    for f in range(f0, f1):
        t_local = f / fps - sh["start"]
        frame = R.render(i, max(0.0, t_local))
        proc.stdin.write(np.ascontiguousarray(frame).tobytes())
    proc.stdin.close()
    if proc.wait() != 0:
        raise RuntimeError(f"ffmpeg failed for shot {sh['id']}")
    os.replace(tmp, out_path)
    return sh["id"], f1 - f0, time.time() - t0


def render_audio(tl, out_dir, music_gain_db=0.0):
    placements = [(ln["g0"], ln["wav"]) for s in tl["shots"] for ln in s.get("lines", [])]
    dlg = assemble_track(placements, tl["total_duration"])
    st = mix(dlg, tl["total_duration"], tl.get("music", {}).get("mood", "night_reflective"),
             ambient=tl.get("ambient"), sfx_events=tl.get("sfx_events", []), swell_at=tl.get("music_swell_at"),
             music_gain_db=music_gain_db + tl.get("music", {}).get("gain_db", 0.0),
             stems_out=str(out_dir / "stem"))
    wav = out_dir / "mix.wav"
    sf.write(wav, st, SR, subtype="PCM_24")
    return wav


def write_srt(tl, path, english=False):
    def ts(x):
        h, r = divmod(x, 3600)
        m, s = divmod(r, 60)
        return f"{int(h):02d}:{int(m):02d}:{int(s):02d},{int(round((s - int(s)) * 1000)):03d}"
    out, k = [], 1
    for s in tl["shots"]:
        for ln in s.get("lines", []):
            txt = ln.get("en") if english else ln["roman"]
            if not txt:
                continue
            out.append(f"{k}\n{ts(ln['g0'])} --> {ts(ln['g1'] + 0.2)}\n{txt}\n")
            k += 1
    Path(path).write_text("\n".join(out), encoding="utf-8")


def render_episode(ep, preset="final", jobs=None, only_shots=None, log=print, music_gain_db=0.0):
    out_dir = ROOT / "outputs" / ep["id"]
    seg_dir = ROOT / "cache" / "segments"
    out_dir.mkdir(parents=True, exist_ok=True)
    seg_dir.mkdir(parents=True, exist_ok=True)
    log(f"[1/4] voices + timeline for {ep['id']}")
    tl = resolve_timeline(ep, log=log)
    save_json(tl, out_dir / "timeline.json")
    log(f"      total {tl['total_duration']:.2f}s, voices: " +
        ", ".join(f"{k}={v['profile']}{' (PREVIEW)' if v['preview'] else ''}" for k, v in tl['voice_info'].items()))
    log("[2/4] audio mix")
    wav = render_audio(tl, out_dir, music_gain_db)
    log("[3/4] video segments")
    tasks, segs = [], []
    for i, sh in enumerate(tl["shots"]):
        key = shot_key(tl, i, preset)
        seg = seg_dir / f"{ep['id']}_{sh['id']}_{preset}_{key}.mp4"
        segs.append(seg)
        force = only_shots and sh["id"] in only_shots
        if seg.exists() and not force:
            log(f"      {sh['id']}: cached")
            continue
        tasks.append((tl, i, preset, seg))
    jobs = jobs or max(1, min(len(tasks), (os.cpu_count() or 2)))
    if tasks:
        with ProcessPoolExecutor(max_workers=jobs) as ex:
            for sid, nf, dt in ex.map(_render_segment, tasks):
                log(f"      {sid}: {nf} frames in {dt:.1f}s")
    log("[4/4] assemble + loudness normalise")
    lst = out_dir / "segments.txt"
    lst.write_text("".join(f"file '{s}'\n" for s in segs))
    suffix = "" if preset == "final" else "_preview"
    final = out_dir / f"{ep['id']}{suffix}.mp4"
    silent = out_dir / "video_only.mp4"
    subprocess.run(["ffmpeg", "-y", "-loglevel", "error", "-f", "concat", "-safe", "0", "-i", str(lst), "-c", "copy",
                    str(silent)], check=True)
    subprocess.run(["ffmpeg", "-y", "-loglevel", "error", "-i", str(silent), "-i", str(wav),
                    "-map", "0:v", "-map", "1:a", "-c:v", "copy",
                    "-af", "loudnorm=I=-14:TP=-1.5:LRA=11,aresample=48000", "-c:a", "aac", "-b:a", "192k",
                    "-ar", "48000", "-movflags", "+faststart", "-shortest", "-t", f"{tl['total_duration']:.3f}",
                    str(final)], check=True)
    silent.unlink(missing_ok=True)
    write_srt(tl, out_dir / f"{ep['id']}_hinglish.srt")
    write_srt(tl, out_dir / f"{ep['id']}_english.srt", english=True)
    # copy script/caption for convenience
    src = Path(ep["_dir"])
    for name in ("episode.yaml", "script.md"):
        if (src / name).exists():
            shutil.copy(src / name, out_dir / name)
    log(f"      -> {final}")
    return final, tl
