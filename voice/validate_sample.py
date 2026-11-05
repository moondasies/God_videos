"""Validate a voice sample before it is used for cloning.

Checks: file exists, consent record present & confirmed, duration, sample rate, clipping,
noise floor / SNR estimate, silence ratio, channel count.

    python -m voice.validate_sample private/voices/girl/sample.wav --consent private/voices/girl/consent.yaml
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

import numpy as np
import soundfile as sf
import yaml

MIN_SECONDS = 6.0
RECOMMENDED_SECONDS = 30.0


def check_consent(consent_path):
    """Consent file must state who owns the voice and that permission is granted.

    Example (private/voices/girl/consent.yaml):
        speaker_name: "<your name>"
        relationship: self            # self | licensed | commissioned
        permission_confirmed: true
        scope: "Mahadev & Me channel, synthetic dialogue"
        date: 2026-11-05
    """
    if not consent_path:
        return False, "no consent file given (required)"
    p = Path(consent_path)
    if not p.exists():
        return False, f"consent file not found: {p}"
    data = yaml.safe_load(p.read_text()) or {}
    if data.get("permission_confirmed") is not True:
        return False, "permission_confirmed is not true"
    if data.get("relationship") not in ("self", "licensed", "commissioned"):
        return False, "relationship must be self | licensed | commissioned"
    if not data.get("speaker_name"):
        return False, "speaker_name missing"
    return True, f"consent OK ({data['relationship']}: {data['speaker_name']})"


def analyse(path):
    audio, sr = sf.read(str(path), dtype="float32", always_2d=True)
    ch = audio.shape[1]
    x = audio.mean(axis=1)
    dur = len(x) / sr
    clip_ratio = float(np.mean(np.abs(x) > 0.99))
    frame = int(0.03 * sr)
    n = max(1, len(x) // frame)
    rms = np.sqrt(np.mean(x[: n * frame].reshape(n, frame) ** 2, axis=1) + 1e-12)
    db = 20 * np.log10(rms + 1e-9)
    noise_floor = float(np.percentile(db, 10))
    speech_level = float(np.percentile(db, 90))
    silence_ratio = float(np.mean(db < noise_floor + 6))
    return dict(duration_s=round(dur, 2), sample_rate=sr, channels=ch,
                clipping_ratio=round(clip_ratio, 5), noise_floor_db=round(noise_floor, 1),
                speech_level_db=round(speech_level, 1), snr_estimate_db=round(speech_level - noise_floor, 1),
                silence_ratio=round(silence_ratio, 3))


def validate(path, consent=None):
    issues, warnings = [], []
    p = Path(path)
    if not p.exists():
        return dict(ok=False, issues=[f"sample not found: {p}"], warnings=[], metrics={})
    ok_c, msg = check_consent(consent)
    if not ok_c:
        issues.append("CONSENT: " + msg)
    try:
        m = analyse(p)
    except Exception as e:  # unreadable file
        return dict(ok=False, issues=issues + [f"cannot read audio: {e}"], warnings=[], metrics={})
    if m["duration_s"] < MIN_SECONDS:
        issues.append(f"too short: {m['duration_s']}s (< {MIN_SECONDS}s)")
    elif m["duration_s"] < RECOMMENDED_SECONDS:
        warnings.append(f"{m['duration_s']}s works for a first experiment; 30-120s of clean speech improves stability")
    if m["sample_rate"] < 16000:
        issues.append(f"sample rate {m['sample_rate']} Hz too low (need >= 16 kHz, ideally 44.1/48 kHz)")
    if m["clipping_ratio"] > 0.001:
        issues.append(f"clipping detected ({m['clipping_ratio'] * 100:.2f}% samples) – re-record with lower gain")
    if m["snr_estimate_db"] < 20:
        warnings.append(f"noisy recording (SNR ~{m['snr_estimate_db']} dB) – record in a quiet, soft-furnished room")
    if m["silence_ratio"] > 0.5:
        warnings.append("more than half the file is silence – trim it")
    if m["channels"] > 1:
        warnings.append("stereo file – will be down-mixed to mono")
    return dict(ok=not issues, issues=issues, warnings=warnings, metrics=m, consent=msg)


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("sample")
    ap.add_argument("--consent", help="consent.yaml for this voice (required)")
    a = ap.parse_args(argv)
    rep = validate(a.sample, a.consent)
    print(json.dumps(rep, indent=2))
    return 0 if rep["ok"] else 1


if __name__ == "__main__":
    sys.exit(main())
