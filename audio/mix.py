"""Mix dialogue + music + ambience + SFX into one stereo track with speech ducking."""
from __future__ import annotations

import numpy as np
import soundfile as sf

from . import dsp, music
from .dsp import SR


def duck_curve(dialogue, depth_db=-10.0, attack=0.12, release=0.5):
    env = dsp.envelope(dialogue, SR, 0.05)
    speech = (env > 0.01).astype(np.float32)
    # smooth attack/release
    out = np.zeros_like(speech)
    a, r = 1 / (attack * SR), 1 / (release * SR)
    v = 0.0
    for i in range(0, len(speech), 64):  # block-wise smoothing is plenty
        tgt = speech[i]
        v += (tgt - v) * min(1.0, (a if tgt > v else r) * 64)
        out[i:i + 64] = v
    g = 10 ** (depth_db / 20)
    return (1 - out * (1 - g)).astype(np.float32)


def mix(dialogue, total_dur, mood, ambient=None, sfx_events=(), swell_at=None, music_gain_db=0.0, stems_out=None):
    n = int(total_dur * SR)
    dlg = np.zeros(n, dtype=np.float32)
    dlg[: min(n, len(dialogue))] = dialogue[:n]
    mus = music.score(total_dur, mood, swell_at=swell_at)[:n] * (10 ** (music_gain_db / 20))
    mus = np.pad(mus, (0, n - len(mus)))
    duck = duck_curve(dlg)
    mus *= duck
    amb = np.zeros(n, dtype=np.float32)
    for kind, start, end in (ambient or []):
        a, b = int(start * SR), int(end * SR)
        seg = music.ambience(kind, (b - a) / SR)
        fl = min(len(seg), int(0.4 * SR))
        if fl:
            seg[:fl] *= np.linspace(0, 1, fl)
            seg[-fl:] *= np.linspace(1, 0, fl)
        amb[a:a + len(seg)] += seg[: n - a]
    amb *= 0.6 + 0.4 * duck
    fx = np.zeros(n, dtype=np.float32)
    for kind, t in sfx_events:
        x = music.sfx(kind)
        a = int(t * SR)
        if a < n:
            fx[a:a + len(x)] += x[: n - a]
    fx *= 0.45 + 0.55 * duck
    # stereo: dialogue centred, music/ambience slightly widened
    wide = np.roll(mus + amb, int(0.011 * SR))
    L = dlg + mus + amb + fx
    R = dlg + 0.85 * (mus + amb) + 0.15 * wide + fx
    st = np.stack([L, R], axis=1)
    pk = np.max(np.abs(st)) + 1e-9
    if pk > 0.95:  # gentle safety
        st = np.tanh(st / pk * 1.1) * 0.95 / np.tanh(1.1)
    if stems_out:
        sf.write(stems_out + "_dialogue.wav", dlg, SR)
        sf.write(stems_out + "_music.wav", mus + amb + fx, SR)
    return st.astype(np.float32)
