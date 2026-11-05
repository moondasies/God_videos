"""Small DSP helpers (numpy/scipy only)."""
from __future__ import annotations

from math import gcd

import numpy as np
from scipy import signal

SR = 48000


def to_mono(x):
    x = np.asarray(x, dtype=np.float32)
    return x.mean(axis=1) if x.ndim == 2 else x


def resample(x, sr_in, sr_out=SR):
    if sr_in == sr_out:
        return x.astype(np.float32)
    g = gcd(int(sr_in), int(sr_out))
    return signal.resample_poly(x, sr_out // g, sr_in // g).astype(np.float32)


def rms_db(x):
    return 20 * np.log10(np.sqrt(np.mean(np.square(x))) + 1e-9)


def peak_db(x):
    return 20 * np.log10(np.max(np.abs(x)) + 1e-9)


def normalize_rms(x, target_db=-20.0, peak_ceiling_db=-1.5):
    voiced = x[np.abs(x) > 0.02] if np.any(np.abs(x) > 0.02) else x
    g = 10 ** ((target_db - rms_db(voiced)) / 20)
    y = x * g
    pk = np.max(np.abs(y)) + 1e-9
    ceiling = 10 ** (peak_ceiling_db / 20)
    if pk > ceiling:
        y = y * (ceiling / pk)
    return y.astype(np.float32)


def trim_silence(x, sr, thresh_db=-42, pad=0.04):
    env = np.abs(x)
    th = 10 ** (thresh_db / 20)
    idx = np.where(env > th)[0]
    if len(idx) == 0:
        return x
    a = max(0, idx[0] - int(pad * sr))
    b = min(len(x), idx[-1] + int(pad * sr))
    return x[a:b]


def fade(x, sr, fin=0.01, fout=0.03):
    x = x.copy()
    n1, n2 = int(fin * sr), int(fout * sr)
    if n1:
        x[:n1] *= np.linspace(0, 1, n1)
    if n2:
        x[-n2:] *= np.linspace(1, 0, n2)
    return x


def low_shelf(x, sr, freq=220, gain_db=2.5):
    """Simple warmth: add a low-passed copy."""
    b, a = signal.butter(2, freq / (sr / 2), "low")
    lo = signal.lfilter(b, a, x)
    return (x + lo * (10 ** (gain_db / 20) - 1)).astype(np.float32)


def deess(x, sr, freq=6500, amount=0.35):
    b, a = signal.butter(2, freq / (sr / 2), "high")
    hi = signal.lfilter(b, a, x)
    return (x - hi * amount).astype(np.float32)


def room(x, sr, wet=0.08, decay=0.45, seed=3):
    """Very subtle synthetic room (no theatrical echo)."""
    n = int(decay * sr)
    rng = np.random.default_rng(seed)
    ir = rng.standard_normal(n) * np.exp(-np.linspace(0, 7, n))
    ir[: int(0.012 * sr)] = 0
    ir /= np.sqrt(np.sum(ir ** 2)) + 1e-9
    w = signal.fftconvolve(x, ir)[: len(x)]
    return ((1 - wet) * x + wet * w).astype(np.float32)


def envelope(x, sr, win=0.05):
    n = max(1, int(win * sr))
    return np.sqrt(signal.fftconvolve(np.square(x), np.ones(n) / n, mode="same").clip(0))
