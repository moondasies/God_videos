"""Generate per-line dialogue audio (cached), mouth cues, and the synchronised dialogue track.

    python -m voice.generate_dialogue episodes/episode_001          # synthesise + report
    python -m voice.generate_dialogue --say mahadev "शांत हो जाओ।"   # quick test line

Each line is synthesised from its Devanagari `tts` text (Hindi TTS frontends need Devanagari;
Roman Hinglish is used only for captions). Lines are cached under cache/voice/ keyed by
text + voice profile + emotion, so editing one line re-synthesises only that line.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import sys
from pathlib import Path

import numpy as np
import soundfile as sf
import yaml

from audio import dsp
from voice.backends import get_backend
from voice.lipsync import mouth_cues

ROOT = Path(__file__).resolve().parent.parent
CACHE = ROOT / "cache" / "voice"
VOICE_VERSION = "3"


def load_voice_config(path=None):
    p = Path(path) if path else ROOT / "config" / "voices.yaml"
    if not p.exists():
        p = ROOT / "voice" / "voice_config.example.yaml"
    return yaml.safe_load(p.read_text())


def resolve_profile(cfg, profile_name):
    prof = dict(cfg["profiles"][profile_name])
    prof["profile_name"] = profile_name
    if prof.get("profile_file"):  # cloned profiles live in private/
        pf = ROOT / prof["profile_file"]
        if pf.exists():
            prof.update(yaml.safe_load(pf.read_text()))
        else:
            raise FileNotFoundError(f"{pf} missing – run voice.clone_voice first, or switch the episode to a preview profile")
    return prof


def postprocess(x, sr, chain):
    for step in chain or []:
        if step == "warmth":
            x = dsp.low_shelf(x, sr, 200, 2.5)
        elif step == "room":
            x = dsp.room(x, sr, wet=0.07)
        elif step == "deess":
            x = dsp.deess(x, sr)
    return x


def synth_line(text, profile, emotion="neutral", allow_paid=False):
    """-> dict(wav=path(48k mono), duration, cues, lipsync_method, cached)"""
    CACHE.mkdir(parents=True, exist_ok=True)
    key_src = json.dumps([VOICE_VERSION, text, {k: v for k, v in profile.items() if k != "source_metrics"}, emotion],
                         sort_keys=True, ensure_ascii=False)
    key = hashlib.sha1(key_src.encode()).hexdigest()[:16]
    wav = CACHE / f"{key}.wav"
    meta = CACHE / f"{key}.json"
    if wav.exists() and meta.exists():
        m = json.loads(meta.read_text())
        m["cached"] = True
        return m
    be = get_backend(profile["backend"], allow_paid=allow_paid)
    audio, sr = be.synthesize(text, profile, emotion)
    audio = dsp.to_mono(audio)
    audio = dsp.resample(audio, sr, dsp.SR)
    audio = dsp.trim_silence(audio, dsp.SR, pad=0.03)
    audio = postprocess(audio, dsp.SR, profile.get("post"))
    audio = dsp.fade(dsp.normalize_rms(audio, profile.get("target_rms_db", -19.0)), dsp.SR)
    sf.write(wav, audio, dsp.SR, subtype="PCM_16")
    cues, method = mouth_cues(wav)
    m = dict(wav=str(wav), duration=round(len(audio) / dsp.SR, 3), cues=cues, lipsync_method=method,
             backend=profile["backend"], profile=profile.get("profile_name"), preview=bool(profile.get("preview")),
             peak_db=round(float(dsp.peak_db(audio)), 2), cached=False)
    meta.write_text(json.dumps(m, ensure_ascii=False, indent=1))
    return m


def assemble_track(placements, total_dur, sr=dsp.SR):
    """placements: [(start_seconds, wav_path)] -> float32 track."""
    track = np.zeros(int(total_dur * sr) + sr, dtype=np.float32)
    for start, path in placements:
        x, _ = sf.read(path, dtype="float32")
        a = int(start * sr)
        track[a:a + len(x)] += x[: max(0, len(track) - a)]
    return track[: int(total_dur * sr)]


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("episode", nargs="?")
    ap.add_argument("--say", nargs=2, metavar=("SPEAKER", "TEXT"))
    ap.add_argument("--out", default="outputs/voice_test.wav")
    a = ap.parse_args(argv)
    cfg = load_voice_config()
    if a.say:
        spk, text = a.say
        prof = resolve_profile(cfg, cfg["defaults"][spk])
        m = synth_line(text, prof, "neutral")
        Path(a.out).parent.mkdir(parents=True, exist_ok=True)
        x, _ = sf.read(m["wav"])
        sf.write(a.out, x, dsp.SR)
        print(json.dumps({k: v for k, v in m.items() if k != "cues"}, indent=1, ensure_ascii=False), "->", a.out)
        return 0
    from pipeline.episode import load_episode
    ep = load_episode(a.episode)
    for shot in ep["shots"]:
        for ln in shot.get("lines", []):
            prof = resolve_profile(cfg, ep["voices"][ln["speaker"]])
            m = synth_line(ln["tts"], prof, ln.get("emotion", "neutral"))
            print(f"{ln['speaker']:8s} {m['duration']:5.2f}s {'(cached)' if m['cached'] else ''} {ln['roman']}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
