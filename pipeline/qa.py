"""Automated quality checks for a rendered reel (+ targeted auto-fixes).

Every check reports PASS / WARN / FAIL with measured numbers. Nothing is assumed: values come
from ffprobe/ffmpeg analysis of the actual output file, the audio stems and the timeline.
"""
from __future__ import annotations

import hashlib
import json
import re
import subprocess
from pathlib import Path

import numpy as np
import soundfile as sf

from .episode import ROOT, TARGET_MAX, TARGET_MIN

IDENTITY_LOCK = ROOT / "config" / "identity.lock.json"

# phrases that would imply a scriptural/authoritative quotation
SCRIPTURE_MARKERS = [r"\bgita\b", r"\bpuran", r"\bshastra", r"\bved(a|on)?\b", r"\bupanishad", r"\bshlok",
                     r"\bshiv ji ne kaha\b", r"\bkehte hain ki\b", r"\blikha hai\b", r"\bscripture",
                     r"\bmahadev ne kaha\b"]
SENSITIVE = [r"suicid", r"khudkushi", r"self.?harm", r"abuse", r"maar(na|ta)", r"violence", r"depress"]


def identity_hash(identity: dict) -> str:
    return hashlib.sha1(json.dumps(identity, sort_keys=True).encode()).hexdigest()[:16]


def current_identity_hashes():
    from animation.characters import GIRL_IDENTITY, MAHADEV_IDENTITY
    return {"girl": identity_hash(GIRL_IDENTITY), "mahadev": identity_hash(MAHADEV_IDENTITY)}


def lock_identities():
    IDENTITY_LOCK.write_text(json.dumps(current_identity_hashes(), indent=1))


def _probe(path):
    r = subprocess.run(["ffprobe", "-v", "error", "-show_streams", "-show_format", "-of", "json", str(path)],
                       capture_output=True, text=True)
    return json.loads(r.stdout)


def _gray_frames(path, w=54, h=96, fps=10):
    r = subprocess.run(["ffmpeg", "-v", "error", "-i", str(path), "-vf", f"fps={fps},scale={w}:{h},format=gray",
                        "-f", "rawvideo", "-"], capture_output=True)
    a = np.frombuffer(r.stdout, dtype=np.uint8)
    return a.reshape(-1, h, w).astype(np.float32)


def _loudness(path):
    r = subprocess.run(["ffmpeg", "-hide_banner", "-nostats", "-i", str(path), "-map", "0:a", "-af", "ebur128=peak=true",
                        "-f", "null", "-"], capture_output=True, text=True)
    txt = r.stderr
    I = re.findall(r"I:\s+(-?[\d.]+) LUFS", txt)
    tp = re.findall(r"Peak:\s+(-?[\d.]+) dBFS", txt)
    return (float(I[-1]) if I else None), (float(tp[-1]) if tp else None)


class Report:
    def __init__(self):
        self.items = []

    def add(self, area, check, status, detail):
        self.items.append(dict(area=area, check=check, status=status, detail=detail))

    @property
    def passed(self):
        return not any(i["status"] == "FAIL" for i in self.items)


def run_qa(ep, preset="final", log=print, write=True):
    out_dir = ROOT / "outputs" / ep["id"]
    suffix = "" if preset == "final" else "_preview"
    video = out_dir / f"{ep['id']}{suffix}.mp4"
    tl = json.loads((out_dir / "timeline.json").read_text(encoding="utf-8"))
    R = Report()
    exp_w, exp_h, exp_fps = (1080, 1920, 30) if preset == "final" else (540, 960, 24)

    # ---------------- technical
    if not video.exists():
        R.add("technical", "file exists", "FAIL", str(video))
        return _finish(R, ep, out_dir, preset, tl, log, write)
    pr = _probe(video)
    v = next((s for s in pr["streams"] if s["codec_type"] == "video"), {})
    a = next((s for s in pr["streams"] if s["codec_type"] == "audio"), {})
    dur = float(pr["format"]["duration"])
    num, den = map(int, v.get("r_frame_rate", "0/1").split("/"))
    fps = num / max(den, 1)
    R.add("technical", "resolution", "PASS" if (v.get("width"), v.get("height")) == (exp_w, exp_h) else "FAIL",
          f"{v.get('width')}x{v.get('height')} (expected {exp_w}x{exp_h}, 9:16)")
    R.add("technical", "frame rate", "PASS" if abs(fps - exp_fps) < 0.01 else "FAIL", f"{fps:.2f} fps")
    R.add("technical", "video codec", "PASS" if v.get("codec_name") == "h264" and v.get("pix_fmt") == "yuv420p" else "FAIL",
          f"{v.get('codec_name')} {v.get('pix_fmt')} {v.get('profile')}")
    R.add("technical", "audio codec", "PASS" if a.get("codec_name") == "aac" else "FAIL",
          f"{a.get('codec_name')} {a.get('sample_rate')} Hz {a.get('channels')} ch")
    integ = subprocess.run(["ffmpeg", "-v", "error", "-i", str(video), "-f", "null", "-"], capture_output=True, text=True)
    R.add("technical", "decode integrity", "PASS" if not integ.stderr.strip() else "FAIL",
          "decoded without errors" if not integ.stderr.strip() else integ.stderr[:300])

    # ---------------- timing
    R.add("timing", "duration 30-40 s", "PASS" if TARGET_MIN <= dur <= TARGET_MAX else "FAIL", f"{dur:.2f}s")
    nframes = int(v.get("nb_frames", 0) or 0)
    expected = round(tl["total_duration"] * exp_fps)
    R.add("animation", "no missing frames", "PASS" if abs(nframes - expected) <= 2 else "FAIL",
          f"{nframes} frames (expected ~{expected})")

    # ---------------- animation motion / freezes / black
    g = _gray_frames(video)
    diffs = np.abs(np.diff(g, axis=0)).mean(axis=(1, 2)) if len(g) > 1 else np.zeros(1)
    win = 15  # 1.5 s at 10 fps
    frozen = []
    for i in range(0, max(1, len(diffs) - win)):
        if diffs[i:i + win].max() < 0.02:
            frozen.append(i / 10)
    fade_end = tl["total_duration"] - 1.0
    frozen = [t for t in frozen if t < fade_end]
    R.add("animation", "no frozen stretches >1.5 s", "PASS" if not frozen else "FAIL",
          f"min motion per 1.5 s window ok; mean frame delta {diffs.mean():.3f}" if not frozen else f"frozen at {frozen[:5]}")
    per_shot = []
    for s in tl["shots"]:
        a0, a1 = int(s["start"] * 10) + 2, int((s["start"] + s["duration"]) * 10) - 2
        m = float(diffs[a0:a1].mean()) if a1 > a0 else 0.0
        per_shot.append((s["id"], round(m, 3)))
    static = [sid for sid, m in per_shot if m < 0.03]
    R.add("animation", "every shot has visible movement", "PASS" if not static else "FAIL",
          ", ".join(f"{sid}:{m}" for sid, m in per_shot))
    blk = (g.mean(axis=(1, 2)) < 6)
    black_runs = np.where(blk[:-12])[0] if len(blk) > 12 else []
    R.add("animation", "no unintended black frames", "PASS" if len(black_runs) == 0 else "WARN",
          "none before the final fade" if len(black_runs) == 0 else f"{len(black_runs)} dark samples")

    # ---------------- audio
    I, tp = _loudness(video)
    R.add("audio", "integrated loudness", "PASS" if I is not None and -16.5 <= I <= -12.5 else "WARN", f"{I} LUFS (target -14)")
    R.add("audio", "true peak / no clipping", "PASS" if tp is not None and tp <= -0.5 else "FAIL", f"{tp} dBFS")
    dlg_p, mus_p = out_dir / "stem_dialogue.wav", out_dir / "stem_music.wav"
    if dlg_p.exists() and mus_p.exists():
        d, sr = sf.read(dlg_p, dtype="float32")
        m, _ = sf.read(mus_p, dtype="float32")
        n = min(len(d), len(m))
        d, m = d[:n], m[:n]
        mask = np.zeros(n, bool)
        for s in tl["shots"]:
            for ln in s.get("lines", []):
                mask[int(ln["g0"] * sr):int(ln["g1"] * sr)] = True
        if mask.any():
            dr = 10 * np.log10(np.mean(d[mask] ** 2) + 1e-12)
            mr = 10 * np.log10(np.mean(m[mask] ** 2) + 1e-12)
            gap = dr - mr
            R.add("audio", "dialogue audible over music", "PASS" if gap >= 10 else "FAIL",
                  f"speech {dr:.1f} dB vs music {mr:.1f} dB under speech (gap {gap:.1f} dB, need >= 10)")

    # ---------------- voice
    vi = tl.get("voice_info", {})
    for spk, info in vi.items():
        expected = ep["voices"].get(spk)
        R.add("voice", f"{spk}: correct profile", "PASS" if info["profile"] == expected else "FAIL",
              f"{info['profile']} via {info['backend']}")
        R.add("voice", f"{spk}: production voice", "WARN" if info["preview"] else "PASS",
              ("PREVIEW voice – " + info.get("license", "")) if info["preview"] else "approved voice")
    bad_lines = []
    for s in tl["shots"]:
        for ln in s.get("lines", []):
            x, sr = sf.read(ln["wav"], dtype="float32")
            env = np.abs(x)
            frame = int(0.02 * sr)
            nfr = len(x) // frame
            db = 20 * np.log10(np.sqrt((x[: nfr * frame].reshape(nfr, frame) ** 2).mean(1)) + 1e-9)
            silent = db < -45
            longest, cur = 0, 0
            for sv in silent:
                cur = cur + 1 if sv else 0
                longest = max(longest, cur)
            tail = float(env[-int(0.015 * sr):].max())
            if longest * 0.02 > 1.0 or tail > 0.25 or env.max() > 0.999 or ln["audio_dur"] < 0.4:
                bad_lines.append(f"{s['id']}:{ln['roman'][:24]} (gap {longest * 0.02:.2f}s tail {tail:.2f})")
    R.add("voice", "no clipped words / unexpected silence", "PASS" if not bad_lines else "FAIL",
          "all lines clean" if not bad_lines else "; ".join(bad_lines))

    # ---------------- lip-sync
    from animation.rig import viseme_params
    cors = []
    for s in tl["shots"]:
        for ln in s.get("lines", []):
            if ln.get("vo"):
                continue
            x, sr = sf.read(ln["wav"], dtype="float32")
            step = 1 / 30
            n = int(ln["audio_dur"] / step)
            if n < 6:
                continue
            env = np.array([np.sqrt(np.mean(x[int(i * step * sr):int((i + 1) * step * sr)] ** 2) + 1e-12) for i in range(n)])
            mo = []
            for i in range(n):
                t = i * step
                val = "X"
                for cu in ln["cues"]:
                    if cu["start"] <= t:
                        val = cu["value"]
                mo.append(viseme_params(val)["open"])
            mo = np.array(mo)
            if mo.std() > 0 and env.std() > 0:
                cors.append(float(np.corrcoef(mo, env)[0, 1]))
    if cors:
        mc = float(np.mean(cors))
        R.add("lip-sync", "mouth opening tracks speech energy", "PASS" if mc >= 0.3 else "FAIL",
              f"mean correlation {mc:.2f} over {len(cors)} on-screen lines (method: {tl['shots'][1]['lines'][0].get('lipsync', '?') if tl['shots'][1].get('lines') else '?'})")

    # ---------------- subtitles
    from animation.draw import font, text_width
    from animation.scene import CAPTION_MAX_W, CAPTION_Y, caption_chunks
    f = font("Poppins-Bold", 56)
    sub_issues = []
    for s in tl["shots"]:
        for ln in s.get("lines", []):
            txt = ln["roman"]
            if "  " in txt or txt != txt.strip():
                sub_issues.append(f"spacing: {txt}")
            if not re.search(r"[.?!…]$", txt):
                sub_issues.append(f"no end punctuation: {txt}")
            if "english" in tl.get("subtitles", "") and not ln.get("en"):
                sub_issues.append(f"missing English: {txt}")
            for c0, c1, words in caption_chunks(ln):
                w = text_width(" ".join(words), f)
                if w > CAPTION_MAX_W:
                    sub_issues.append(f"too wide ({w:.0f}px): {' '.join(words)}")
                if c1 - c0 < 0.35:
                    sub_issues.append(f"chunk too fast ({c1 - c0:.2f}s): {' '.join(words)}")
    safe = 1920 * 0.13 < CAPTION_Y - 70 and CAPTION_Y + 120 < 1920 * 0.83
    R.add("subtitles", "timing, punctuation & width", "PASS" if not sub_issues else "FAIL",
          "all caption chunks fit, readable >= 0.35 s each" if not sub_issues else "; ".join(sub_issues[:6]))
    R.add("subtitles", "safe-zone placement", "PASS" if safe else "FAIL",
          f"caption band y={CAPTION_Y - 70}-{CAPTION_Y + 120} px of 1920 (keeps clear of top 13% / bottom 17% UI)")

    # ---------------- spiritual accuracy / sensitivity
    flagged = []
    for s in tl["shots"]:
        for ln in s.get("lines", []):
            low = ln["roman"].lower()
            for pat in SCRIPTURE_MARKERS:
                if re.search(pat, low) and not ln.get("source"):
                    flagged.append(f"'{ln['roman']}' looks like a scriptural claim but has no source")
            if ln.get("attribution") not in ("original_fiction", "paraphrase", "scripture"):
                flagged.append(f"missing attribution on '{ln['roman'][:30]}'")
            if ln.get("attribution") == "scripture" and not ln.get("source"):
                flagged.append(f"scripture line without citation: {ln['roman'][:30]}")
    R.add("spiritual", "no fabricated scriptural attribution", "PASS" if not flagged else "FAIL",
          "all lines marked original fiction / cited" if not flagged else "; ".join(flagged))
    text_all = " ".join(ln["roman"].lower() for s in tl["shots"] for ln in s.get("lines", []))
    sens = [p for p in SENSITIVE if re.search(p, text_all)]
    note = tl.get("attribution_note", "")
    R.add("spiritual", "sensitive-topic safeguard", "WARN" if sens and "professional" not in note.lower() else "PASS",
          "sensitive themes need a help-seeking note" if sens and "professional" not in note.lower() else "ok")

    # ---------------- character consistency
    locked = json.loads(IDENTITY_LOCK.read_text()) if IDENTITY_LOCK.exists() else {}
    cur = current_identity_hashes()
    for k, hval in cur.items():
        R.add("character", f"{k}: locked identity spec", "PASS" if locked.get(k) == hval else "FAIL",
              f"hash {hval}" + ("" if locked.get(k) == hval else f" != locked {locked.get(k)}"))
    from animation.characters import WARDROBE
    outfits = {tl.get("characters", {}).get("girl", {}).get("outfit")}
    for s in tl["shots"]:
        o = s.get("actors", {}).get("girl", {}).get("outfit")
        if o:
            outfits.add(o)
    outfits.discard(None)
    R.add("character", "wardrobe continuity", "PASS" if len(outfits) <= 1 and outfits <= set(WARDROBE) else "WARN",
          f"girl outfit(s) in episode: {sorted(outfits)}")
    return _finish(R, ep, out_dir, preset, tl, log, write)


def _finish(R, ep, out_dir, preset, tl, log, write):
    rep = dict(episode=ep["id"], preset=preset, passed=R.passed, checks=R.items,
               voice_status={k: ("PREVIEW (temporary)" if v["preview"] else "approved") for k, v in tl.get("voice_info", {}).items()})
    if write:
        suffix = "" if preset == "final" else "_preview"
        (out_dir / f"qa_report{suffix}.json").write_text(json.dumps(rep, indent=1, ensure_ascii=False))
        md = [f"# QA report – {ep['id']} ({preset})", "", f"**Overall: {'PASSED' if R.passed else 'FAILED'}**", "",
              "| Area | Check | Status | Detail |", "|---|---|---|---|"]
        md += [f"| {i['area']} | {i['check']} | {i['status']} | {str(i['detail']).replace('|', '/')} |" for i in R.items]
        (out_dir / f"qa_report{suffix}.md").write_text("\n".join(md) + "\n", encoding="utf-8")
    for i in R.items:
        log(f"  [{i['status']:4s}] {i['area']:10s} {i['check']}: {i['detail']}")
    log(f"QA {'PASSED' if R.passed else 'FAILED'} for {ep['id']} ({preset})")
    return rep


def run_qa_with_fixes(ep, preset="final", log=print):
    """Render, QA, and attempt targeted fixes (music level) once."""
    from .render import render_episode
    render_episode(ep, preset, log=log)
    rep = run_qa(ep, preset, log=log)
    failed = {i["check"] for i in rep["checks"] if i["status"] == "FAIL"}
    if "dialogue audible over music" in failed or "true peak / no clipping" in failed:
        log("auto-fix: lowering music by 4 dB and re-mixing")
        render_episode(ep, preset, log=log, music_gain_db=-4.0)
        rep = run_qa(ep, preset, log=log)
    return rep
