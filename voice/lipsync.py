"""Mouth cues for a dialogue line.

Primary: Rhubarb Lip Sync (MIT, offline) in its language-independent `phonetic` recogniser,
which suits Hindi better than the English dictionary recogniser.
Fallback: amplitude + spectral heuristics producing the same A-H/X shape set.
"""
from __future__ import annotations

import json
import platform
import shutil
import subprocess
from pathlib import Path

import numpy as np
import soundfile as sf

ROOT = Path(__file__).resolve().parent.parent


def rhubarb_path():
    exe = "rhubarb.exe" if platform.system() == "Windows" else "rhubarb"
    p = ROOT / "models" / "bin" / "rhubarb" / exe
    if p.exists():
        return str(p)
    return shutil.which("rhubarb")


def rhubarb_cues(wav_path):
    exe = rhubarb_path()
    if not exe:
        return None
    r = subprocess.run([exe, "-r", "phonetic", "-f", "json", "--extendedShapes", "GHX", str(wav_path)],
                       capture_output=True, text=True, timeout=300)
    if r.returncode != 0:
        return None
    data = json.loads(r.stdout)
    return [dict(start=c["start"], end=c["end"], value=c["value"]) for c in data["mouthCues"]]


def amplitude_cues(wav_path, step=0.05):
    x, sr = sf.read(str(wav_path), dtype="float32")
    if x.ndim > 1:
        x = x.mean(axis=1)
    n = int(step * sr)
    cues = []
    peak = np.max(np.abs(x)) + 1e-9
    for i in range(0, len(x), n):
        fr = x[i:i + n]
        if len(fr) < 8:
            break
        rms = np.sqrt(np.mean(fr ** 2)) / peak
        spec = np.abs(np.fft.rfft(fr * np.hanning(len(fr))))
        freqs = np.fft.rfftfreq(len(fr), 1 / sr)
        cent = float(np.sum(freqs * spec) / (np.sum(spec) + 1e-9))
        if rms < 0.04:
            v = "X"
        elif rms < 0.12:
            v = "B"
        elif cent > 2500:
            v = "C"
        elif cent < 900:
            v = "E" if rms > 0.3 else "F"
        else:
            v = "D" if rms > 0.35 else "C"
        t0 = i / sr
        if cues and cues[-1]["value"] == v:
            cues[-1]["end"] = t0 + step
        else:
            cues.append(dict(start=round(t0, 3), end=round(t0 + step, 3), value=v))
    return cues


def _shape_at(cues, t):
    v = "X"
    for c in cues:
        if c["start"] <= t:
            v = c["value"]
        else:
            break
    return v


def hybrid_cues(wav_path, step=0.05):
    """Energy decides HOW OPEN the mouth is (robust for Hindi); Rhubarb only contributes
    lip ROUNDING (E/F) and F/V bites (G) where they agree with the energy."""
    amp = amplitude_cues(wav_path, step)
    rh = rhubarb_cues(wav_path)
    if not rh:
        return amp
    out = []
    for c in amp:
        mid = (c["start"] + c["end"]) / 2
        r = _shape_at(rh, mid)
        v = c["value"]
        if v in ("C", "D") and r in ("E", "F"):
            v = "E" if v == "D" else "F"
        elif v == "B" and r == "G":
            v = "G"
        if out and out[-1]["value"] == v:
            out[-1]["end"] = c["end"]
        else:
            out.append(dict(start=c["start"], end=c["end"], value=v))
    return out


def mouth_cues(wav_path, method="hybrid"):
    """method: hybrid (default; measured best on Hindi) | energy | rhubarb"""
    if method == "rhubarb":
        cues = rhubarb_cues(wav_path)
        if cues:
            return cues, "rhubarb"
    if method == "hybrid" and rhubarb_path():
        return hybrid_cues(wav_path), "hybrid(energy+rhubarb)"
    return amplitude_cues(wav_path, 0.05), "energy"
