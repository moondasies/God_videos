"""Procedural, original background music, ambience and sound effects (numpy only).

Nothing here samples or imitates existing recordings: tanpura-like drone (additive synthesis),
soft pads, bell / bansuri-like motifs on a pentatonic (Bhupali-shaped) scale.
"""
from __future__ import annotations

import numpy as np
from scipy import signal

from .dsp import SR

SCALE = [0, 2, 4, 7, 9]  # S R G P D


def _t(n):
    return np.arange(n) / SR


def _env(n, a=0.01, d=1.0, curve=4.0):
    t = _t(n)
    e = np.minimum(1, t / max(a, 1e-4)) * np.exp(-curve * np.maximum(0, t - a) / max(d, 1e-3))
    return e.astype(np.float32)


def _lp(x, f, order=2):
    b, a = signal.butter(order, min(f / (SR / 2), 0.99), "low")
    return signal.lfilter(b, a, x).astype(np.float32)


def _bp(x, lo, hi):
    b, a = signal.butter(2, [lo / (SR / 2), hi / (SR / 2)], "band")
    return signal.lfilter(b, a, x).astype(np.float32)


def note_hz(sa, degree, octave=0):
    o, d = divmod(degree, len(SCALE))
    return sa * 2 ** ((SCALE[d] + 12 * (o + octave)) / 12)


def tanpura(dur, sa=146.83, cycle=4.4, gain=0.18, seed=1):
    n = int(dur * SR)
    out = np.zeros(n + SR * 5, dtype=np.float32)
    rng = np.random.default_rng(seed)
    strings = [sa * 1.5 / 2, sa, sa, sa / 2]  # Pa(low), Sa, Sa, Sa(low)
    t0 = 0.0
    while t0 < dur:
        for i, f in enumerate(strings):
            st = int((t0 + i * cycle / 4) * SR)
            m = int(4.5 * SR)
            tt = _t(m)
            tone = np.zeros(m, dtype=np.float32)
            for h in range(1, 18):
                det = 1 + rng.normal(0, 0.0006)
                amp = (1 / h ** 0.85) * (1 + 0.6 * np.sin(2 * np.pi * (0.4 + 0.07 * h) * tt) * (h > 5))  # jawari shimmer
                tone += (amp * np.sin(2 * np.pi * f * h * det * tt)).astype(np.float32) * np.exp(-tt * (0.6 + 0.06 * h)).astype(np.float32)
            tone *= _env(m, 0.005, 3.0, 1.2)
            out[st:st + m] += (tone * 0.12)[: max(0, len(out) - st)]
        t0 += cycle
    return (_lp(out[:n], 3500) * gain).astype(np.float32)


def pad(dur, sa=146.83, gain=0.12, chords=None, chord_len=6.0):
    n = int(dur * SR)
    tt = _t(n)
    chords = chords or [[0, 2, 3], [0, 3, 4], [-1, 1, 3], [0, 2, 4]]
    out = np.zeros(n, dtype=np.float32)
    for ci in range(int(dur / chord_len) + 1):
        a, b = int(ci * chord_len * SR), int(min(n, (ci + 1) * chord_len * SR + SR * 1.5))
        if a >= n:
            break
        seg = tt[a:b] - tt[a]
        env = np.minimum(1, seg / 1.5) * np.minimum(1, (seg[-1] - seg + 1e-3) / 1.5)
        for deg in chords[ci % len(chords)]:
            f = note_hz(sa, deg, 1)
            for det in (-0.003, 0.003):
                w = np.sin(2 * np.pi * f * (1 + det) * seg) + 0.3 * np.sin(2 * np.pi * 2 * f * (1 + det) * seg)
                out[a:b] += (w * env * 0.18).astype(np.float32)
    lfo = 0.85 + 0.15 * np.sin(2 * np.pi * 0.07 * tt)
    return (_lp(out * lfo, 1800) * gain).astype(np.float32)


def bell(f, length=2.5):
    m = int(length * SR)
    tt = _t(m)
    x = (np.sin(2 * np.pi * f * tt) + 0.4 * np.sin(2 * np.pi * f * 2.76 * tt) * np.exp(-tt * 3)
         + 0.2 * np.sin(2 * np.pi * f * 5.4 * tt) * np.exp(-tt * 6))
    return (x * _env(m, 0.003, length * 0.6, 3)).astype(np.float32)


def flute(f, length=1.2, seed=0):
    m = int(length * SR)
    tt = _t(m)
    vib = 1 + 0.006 * np.sin(2 * np.pi * 5.2 * tt) * np.minimum(1, tt / 0.4)
    ph = 2 * np.pi * np.cumsum(f * vib) / SR
    tone = np.sin(ph) + 0.15 * np.sin(2 * ph) + 0.05 * np.sin(3 * ph)
    breath = _bp(np.random.default_rng(seed).standard_normal(m).astype(np.float32), f * 0.9, f * 3) * 0.25
    env = np.minimum(1, tt / 0.12) * np.minimum(1, (tt[-1] - tt + 1e-3) / 0.25)
    return ((tone + breath) * env * 0.5).astype(np.float32)


def sprinkle(dur, sa, density=0.35, seed=4, gain=0.08, voice="bell", start=0.0, octave=2, swell_at=None):
    n = int(dur * SR)
    out = np.zeros(n + SR * 3, dtype=np.float32)
    rng = np.random.default_rng(seed)
    t = start + rng.uniform(0.5, 1.5)
    deg = rng.integers(0, 5)
    while t < dur - 0.5:
        deg = int(np.clip(deg + rng.choice([-2, -1, 1, 1, 2]), 0, 7))
        f = note_hz(sa, deg, octave)
        x = bell(f) if voice == "bell" else flute(f / 2, rng.uniform(0.6, 1.4), int(t * 10))
        a = int(t * SR)
        out[a:a + len(x)] += x[: len(out) - a]
        dens = density * (1.8 if swell_at is not None and t > swell_at else 1.0)
        t += rng.uniform(0.8, 2.2) / dens
    return out[:n] * gain


MOODS = {
    "night_reflective": dict(sa=146.83, tanpura=0.07, pad=0.045, bells=0.022, flute=0.0, density=0.3),
    "sunset_tender": dict(sa=138.59, tanpura=0.065, pad=0.04, bells=0.016, flute=0.022, density=0.25),
    "dream": dict(sa=155.56, tanpura=0.045, pad=0.06, bells=0.026, flute=0.0, density=0.45),
    "hopeful": dict(sa=164.81, tanpura=0.06, pad=0.05, bells=0.022, flute=0.018, density=0.35),
}


def score(dur, mood="night_reflective", swell_at=None, seed=1):
    m = MOODS.get(mood, MOODS["night_reflective"])
    x = tanpura(dur, m["sa"], gain=m["tanpura"], seed=seed)
    x += pad(dur, m["sa"], gain=m["pad"])
    x += sprinkle(dur, m["sa"], m["density"], seed + 3, m["bells"], "bell", swell_at=swell_at)
    if m["flute"]:
        x += sprinkle(dur, m["sa"], m["density"] * 0.6, seed + 9, m["flute"], "flute", start=2.0, octave=1, swell_at=swell_at)
    if swell_at is not None:  # gentle lift at the realisation
        tt = _t(len(x))
        x *= (1 + 0.35 * np.clip((tt - swell_at) / 2.5, 0, 1)).astype(np.float32)
    # global fade in/out
    n = len(x)
    fi, fo = int(1.2 * SR), int(2.5 * SR)
    x[:fi] *= np.linspace(0, 1, fi)
    x[-fo:] *= np.linspace(1, 0, fo)
    return x.astype(np.float32)


# ---------------------------------------------------------------- ambience
def ambience(kind, dur, seed=7):
    n = int(dur * SR)
    rng = np.random.default_rng(seed)
    tt = _t(n)
    if kind == "night_crickets":
        out = np.zeros(n, dtype=np.float32)
        for k in range(3):
            f = 4300 + k * 350
            chirp = (np.sin(2 * np.pi * 28 * tt + k) > 0.6).astype(np.float32)
            slow = (np.sin(2 * np.pi * (0.45 + 0.1 * k) * tt + k * 2) > 0.2).astype(np.float32)
            out += np.sin(2 * np.pi * f * tt).astype(np.float32) * _lp(chirp * slow, 200) * 0.02
        return out
    if kind in ("rooftop_wind", "mountain_wind"):
        noise = np.cumsum(rng.standard_normal(n)).astype(np.float32)
        noise -= _lp(noise, 2)
        w = _lp(noise, 500) / (np.std(noise) + 1e-9)
        return w * (0.5 + 0.5 * np.sin(2 * np.pi * 0.08 * tt)).astype(np.float32) * 0.03
    if kind == "rain":
        return _bp(rng.standard_normal(n).astype(np.float32), 800, 6000) * 0.03
    if kind in ("cafe_murmur", "city", "office_hum"):
        return _lp(rng.standard_normal(n).astype(np.float32), 600) * 0.03
    if kind == "birds":
        out = np.zeros(n, dtype=np.float32)
        for _ in range(int(dur / 2)):
            a = int(rng.uniform(0, max(dur - 1, 0.1)) * SR)
            m = int(0.15 * SR)
            f = rng.uniform(2500, 4000)
            seg = np.sin(2 * np.pi * np.cumsum(f * (1 + 0.3 * np.sin(np.linspace(0, 6, m)))) / SR) * _env(m, 0.01, 0.1)
            out[a:a + m] += seg[: n - a].astype(np.float32) * 0.03
        return out
    return np.zeros(n, dtype=np.float32)


# ---------------------------------------------------------------- SFX
def sfx(kind, seed=3):
    rng = np.random.default_rng(seed)
    if kind == "divine_shimmer":
        L = 2.6
        n = int(L * SR)
        out = np.zeros(n, dtype=np.float32)
        for i, deg in enumerate([0, 2, 4, 5, 7, 9, 10]):
            x = bell(note_hz(293.66, deg, 1), 2.0) * 0.5
            a = int(i * 0.09 * SR)
            out[a:a + len(x)] += x[: n - a]
        whoosh = _bp(rng.standard_normal(n).astype(np.float32), 2000, 9000) * np.sin(np.linspace(0, np.pi, n)) * 0.15
        return (out + whoosh) * 0.16
    if kind == "phone_scroll":
        n = int(2.5 * SR)
        out = np.zeros(n, dtype=np.float32)
        for t in (0.25, 1.0, 1.75):
            m = int(0.25 * SR)
            sw = _bp(rng.standard_normal(m).astype(np.float32), 1500, 6000) * _env(m, 0.02, 0.08) * 0.25
            a = int(t * SR)
            out[a:a + m] += sw
        return out
    if kind == "message_pop":
        m = int(0.3 * SR)
        tt = _t(m)
        return (np.sin(2 * np.pi * (880 + 600 * tt) * tt) * _env(m, 0.003, 0.08) * 0.35).astype(np.float32)
    if kind == "soft_whoosh":
        m = int(0.9 * SR)
        return (_bp(rng.standard_normal(m).astype(np.float32), 300, 3000) * np.sin(np.linspace(0, np.pi, m)) ** 2 * 0.2).astype(np.float32)
    if kind == "bloom_chime":
        out = np.zeros(int(3 * SR), dtype=np.float32)
        for i, deg in enumerate([4, 7, 9, 12]):
            x = bell(note_hz(261.63, deg, 1), 2.4) * 0.12
            a = int(i * 0.35 * SR)
            out[a:a + len(x)] += x[: len(out) - a]
        return out
    if kind == "sigh":
        m = int(1.0 * SR)
        return (_bp(rng.standard_normal(m).astype(np.float32), 300, 1800) * _env(m, 0.15, 0.6, 2) * 0.12).astype(np.float32)
    raise KeyError(kind)
