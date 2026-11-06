"""Pilot reel v2: painted sheet art + user's own voice recordings -> 9:16 anime/webtoon-style MP4.

    python -m anime.pilot                 # full build (audio prep, assets, render, QA)
    python -m anime.pilot --preview       # 540x960 quick check

Inputs (git-ignored, see docs/inputs.md):
    private/characters/sheet.webp                    approved character sheet (both characters)
    private/audio/pilot/L01_girl_raw.*               girl's recording
    private/audio/pilot/L02_mahadev_raw.*            Mahadev's recording (music bed is removed)
Everything runs offline on CPU with free, open models.
"""
from __future__ import annotations

import argparse
import json
import math
import random
import subprocess
import time
from concurrent.futures import ProcessPoolExecutor
from functools import lru_cache
from pathlib import Path

import cv2
import numpy as np
import soundfile as sf

ROOT = Path(__file__).resolve().parent.parent
PRIV = ROOT / "private" / "audio" / "pilot"
OUTDIR = ROOT / "outputs" / "pilot_v2"
CACHE = ROOT / "cache" / "pilot_v2"
W, H = 1080, 1920
SR = 48000
OUTFIT = "rose_blazer"

# ----------------------------------------------------------------------------- audio plan
# Girl recording: (start, end) spans in the raw file, joined with the given gaps (seconds).
GIRL_SPANS = [(1.10, 6.33), (7.89, 13.78), (14.02, 15.88)]
GIRL_GAPS = [0.45, 0.24]
MAHADEV_SPAN = (0.0, None)          # trimmed automatically at the trailing whoosh/silence
GIRL_START = 1.6
CAPTIONS_GIRL = [
    "Mera naam Srijita hai, main 22 saal ki hoon, aur mujhe",
    "Mahadev bahut pasand hai. Mujhe Mahadev se baatein karna, mujhe unki baatein sunna, mujhe inke baare mein sunna,",
    "Mujhe ye saari cheezein bahut pasand hain.",
]
CAPTION_MAHADEV = "Jo bhi meri pooja karega, use pariksha to deni hogi."


def _ff_to_wav(src, dst, extra_af=None, ss=None, to=None):
    cmd = ["ffmpeg", "-y", "-v", "error"]
    if ss is not None:
        cmd += ["-ss", f"{ss:.3f}"]
    if to is not None:
        cmd += ["-to", f"{to:.3f}"]
    cmd += ["-i", str(src), "-ac", "1", "-ar", str(SR)]
    if extra_af:
        cmd += ["-af", extra_af]
    cmd += [str(dst)]
    subprocess.run(cmd, check=True)


def _find(prefix):
    c = sorted(PRIV.glob(prefix + "*"))
    if not c:
        raise SystemExit(f"missing {PRIV}/{prefix}.*  (see docs/inputs.md)")
    return c[0]


def _norm(x, target_db=-18.0, ceil_db=-1.5):
    v = x[np.abs(x) > 0.01]
    rms = np.sqrt(np.mean((v if len(v) else x) ** 2)) + 1e-9
    y = x * (10 ** (target_db / 20) / rms)
    pk = np.abs(y).max() + 1e-9
    if pk > 10 ** (ceil_db / 20):
        y *= 10 ** (ceil_db / 20) / pk
    return y.astype(np.float32)


def _tighten_pauses(x, max_gap=0.55, thresh_ratio=0.04):
    """Shorten internal silences longer than max_gap (keeps natural breath, removes dead air)."""
    win = int(0.03 * SR)
    env = np.convolve(np.abs(x), np.ones(win) / win, "same")
    quiet = env < env.max() * thresh_ratio
    out, i, n = [], 0, len(x)
    while i < n:
        if quiet[i]:
            j = i
            while j < n and quiet[j]:
                j += 1
            gap = j - i
            keep = min(gap, int(max_gap * SR)) if 0 < i and j < n else gap
            if keep < gap:
                h = keep // 2
                seg = np.concatenate([x[i:i + h], x[j - (keep - h):j]])
            else:
                seg = x[i:j]
            out.append(seg)
            i = j
        else:
            j = i
            while j < n and not quiet[j]:
                j += 1
            out.append(x[i:j])
            i = j
    return np.concatenate(out).astype(np.float32)


def prepare_audio(log=print):
    CACHE.mkdir(parents=True, exist_ok=True)
    # ---- girl: clean (denoise + rumble cut + gentle compression), trim the meta parts, tighten pauses
    g_raw = _find("L01_girl")
    clean = CACHE / "girl_clean.wav"
    _ff_to_wav(g_raw, clean, "highpass=f=85,afftdn=nr=14:nf=-50:tn=1,acompressor=threshold=-24dB:ratio=2.5:attack=8:release=120,"
                             "equalizer=f=3200:t=q:w=1.2:g=2")
    x, _ = sf.read(clean, dtype="float32")
    parts, spans = [], []
    t = GIRL_START
    for i, (a, b) in enumerate(GIRL_SPANS):
        seg = x[int(a * SR):int(b * SR)].copy()
        f = int(0.015 * SR)
        seg[:f] *= np.linspace(0, 1, f)
        seg[-f:] *= np.linspace(1, 0, f)
        parts.append(seg)
        spans.append((round(t, 3), round(t + len(seg) / SR, 3)))
        t += len(seg) / SR
        if i < len(GIRL_GAPS):
            parts.append(np.zeros(int(GIRL_GAPS[i] * SR), np.float32))
            t += GIRL_GAPS[i]
    girl = _norm(np.concatenate(parts), -18.5)
    # ---- mahadev: isolate the voice from the music bed with MDX-Net (Kim_Vocal_2), then clean
    m_raw = _find("L02_mahadev")
    voc_p = CACHE / "mahadev_vocals44.wav"
    if not voc_p.exists():
        from .separate import separate_vocals
        log("  isolating Mahadev's voice from the music bed (MDX-Net Kim_Vocal_2)...")
        voc, sr = separate_vocals(m_raw)
        sf.write(voc_p, voc.T, sr)
    m_clean = CACHE / "mahadev_clean.wav"
    _ff_to_wav(voc_p, m_clean, "highpass=f=70,afftdn=nr=10:nf=-48:tn=1,acompressor=threshold=-22dB:ratio=2:attack=10:release=150,"
                               "equalizer=f=180:t=q:w=1:g=2.5")
    m, _ = sf.read(m_clean, dtype="float32")
    env = np.convolve(np.abs(m), np.ones(int(0.05 * SR)) / int(0.05 * SR), "same")
    voiced = np.where(env > env.max() * 0.06)[0]
    a = max(0, voiced[0] - int(0.05 * SR))
    b = min(len(m), voiced[-1] + int(0.12 * SR))
    # the end of the clip is a whoosh/music tail: cut at the last speech-band energy
    m = m[a:b]
    m = _tighten_pauses(m, max_gap=0.55)
    f = int(0.03 * SR)
    m[-f:] *= np.linspace(1, 0, f)
    m = _norm(m, -17.5)
    return girl, spans, m


# ----------------------------------------------------------------------------- shot plan
def shot_plan(girl_spans, girl_len, m_len):
    g0 = GIRL_START
    gA, gB, gC = girl_spans
    m_start = gC[1] + 1.45                         # Mahadev appears, then speaks
    m_end = m_start + m_len
    split = m_start + m_len * 0.47
    shots = [
        dict(id="s00", kind="wide_girl", t0=0.0, t1=gA[0], bg_blur=5, title=True),
        dict(id="s01", kind="girl_medium", t0=gA[0], t1=gB[0], speaking="girl", zoom=(1.0, 1.06)),
        dict(id="s02", kind="cutaway", asset="detail_moon", t0=gB[0], t1=gB[0] + 2.0, vo="girl"),
        dict(id="s03", kind="girl_close", t0=gB[0] + 2.0, t1=gB[0] + 4.1, speaking="girl", zoom=(1.0, 1.05)),
        dict(id="s04", kind="girl_dream", asset="girl_happy_closed", t0=gB[0] + 4.1, t1=gB[1], vo="girl"),
        dict(id="s05", kind="girl_medium", t0=gB[1], t1=gC[1] + 0.25, speaking="girl", zoom=(1.03, 1.08), tilt=1.5),
        dict(id="s06", kind="mahadev_appear", t0=gC[1] + 0.25, t1=m_start + 0.5, transition="glow"),
        dict(id="s07", kind="mahadev_medium", t0=m_start + 0.5, t1=split, speaking="mahadev", zoom=(1.0, 1.05)),
        dict(id="s08", kind="mahadev_close", t0=split, t1=m_end + 0.35, speaking="mahadev", zoom=(1.0, 1.06)),
        dict(id="s09", kind="girl_react", asset="girl_surprised", t0=m_end + 0.35, t1=m_end + 3.2),
        dict(id="s10", kind="two_shot_wide", t0=m_end + 3.2, t1=m_end + 6.9, bg_blur=4, zoom=(1.0, 1.12)),
        dict(id="s11", kind="end_card", t0=m_end + 6.9, t1=m_end + 11.4, fade_out=0.8),
    ]
    return shots, (m_start, m_end)


# ----------------------------------------------------------------------------- rendering helpers
def _bg_plate(blur, warm=0.0, night=0.0):
    """Painted-feel backdrop: procedural rooftop at dusk, heavily defocused (depth of field)."""
    key = CACHE / f"bg_{blur}_{warm}_{night}.png"
    if key.exists():
        return cv2.cvtColor(cv2.imread(str(key)), cv2.COLOR_BGR2RGB).astype(np.float32) / 255
    import skia
    from animation.backgrounds import H as BH, PAD, W as BW, get_background, layer_image
    bg = get_background("rooftop_sunset")
    surf = skia.Surface(W, H)
    c = surf.getCanvas()
    c.scale(W / BW, H / BH)
    for i, layer in enumerate(bg["layers"]):
        c.save()
        if layer.live:
            layer.fn(c, 3.0)
        else:
            c.drawImageRect(layer_image("rooftop_sunset", i, layer, 1.0),
                            skia.Rect.MakeLTRB(-PAD, -PAD, BW + PAD, BH + PAD))
        c.restore()
    img = surf.makeImageSnapshot().toarray(colorType=skia.kRGBA_8888_ColorType)[..., :3].astype(np.float32) / 255
    if blur:
        img = cv2.GaussianBlur(img, (0, 0), blur)
    # painterly bloom + grade
    bloom = cv2.GaussianBlur(np.clip(img - 0.55, 0, 1), (0, 0), 40)
    img = np.clip(img + bloom * 0.6, 0, 1)
    if night:
        img = img * np.array([0.72, 0.74, 0.95]) * (1 - 0.25 * night) + np.array([0.02, 0.02, 0.08]) * night
    if warm:
        img = np.clip(img * np.array([1.0 + 0.06 * warm, 1.0, 1.0 - 0.06 * warm]), 0, 1)
    cv2.imwrite(str(key), cv2.cvtColor((img * 255).astype(np.uint8), cv2.COLOR_RGB2BGR))
    return img.astype(np.float32)


def _over(dst, src_rgba, M, alpha_mul=1.0):
    """Affine-place an RGBA float image onto dst (HxWx3 float)."""
    warped = cv2.warpAffine(src_rgba, M, (dst.shape[1], dst.shape[0]), flags=cv2.INTER_LINEAR,
                            borderMode=cv2.BORDER_CONSTANT, borderValue=(0, 0, 0, 0))
    a = warped[..., 3:4] * alpha_mul
    dst[:] = dst * (1 - a) + warped[..., :3] * a
    return warped


def _place(img_w, img_h, cx, cy, height_px, zoom=1.0, focus=(0.5, 0.5)):
    """Affine matrix: scale image so it is height_px tall, its focus point lands at (cx, cy); zoom about focus."""
    s = height_px / img_h * zoom
    fx, fy = focus[0] * img_w, focus[1] * img_h
    return np.float32([[s, 0, cx - fx * s], [0, s, cy - fy * s]])


def _particles(dst, t, n=55, seed=3, color=(1.0, 0.86, 0.55), strength=0.7, rise=40, size=(2, 6)):
    r = random.Random(seed)
    layer = np.zeros((H // 2, W // 2), np.float32)
    for i in range(n):
        x = (r.uniform(0, W) + math.sin(t * 0.5 + i) * 30) % W
        y = (r.uniform(0, H) - t * r.uniform(rise * 0.5, rise * 1.5)) % H
        rad = r.uniform(*size)
        tw = 0.5 + 0.5 * math.sin(t * r.uniform(1, 3) + i)
        cv2.circle(layer, (int(x / 2), int(y / 2)), max(1, int(rad / 2)), 0.6 + 0.4 * tw, -1, cv2.LINE_AA)
    layer = cv2.GaussianBlur(layer, (0, 0), 1.6)
    layer = cv2.resize(layer, (W, H), interpolation=cv2.INTER_LINEAR)[..., None]
    dst[:] = np.clip(dst + layer * np.array(color, np.float32) * strength, 0, 1)


def _glow(dst, cx, cy, radius, color, strength):
    yy, xx = np.ogrid[0:H, 0:W]
    d = np.sqrt((xx - cx) ** 2 + (yy - cy) ** 2) / radius
    g = np.clip(1 - d, 0, 1) ** 2
    dst[:] = np.clip(dst + g[..., None] * np.array(color, np.float32) * strength, 0, 1)


_VIG = None


def _vignette(dst, k=0.42):
    global _VIG
    if _VIG is None:
        yy, xx = np.ogrid[0:H, 0:W]
        d = np.sqrt(((xx - W / 2) / (W * 0.75)) ** 2 + ((yy - H * 0.46) / (H * 0.62)) ** 2)
        _VIG = np.clip(1 - k * np.clip(d - 0.45, 0, 1) * 1.6, 0, 1).astype(np.float32)[..., None]
    dst *= _VIG


def _panel(dst, rgb, t, cx, cy, width):
    """Illustrative cutaway: the sheet's painted detail as a floating card."""
    h, w = rgb.shape[:2]
    s = width / w * (1 + 0.04 * t)
    card = np.dstack([rgb[..., :3], np.ones((h, w), np.float32)])
    rr = int(min(h, w) * 0.08)
    mask = np.zeros((h, w), np.float32)
    cv2.rectangle(mask, (rr, 0), (w - rr, h), 1, -1)
    cv2.rectangle(mask, (0, rr), (w, h - rr), 1, -1)
    for px, py in ((rr, rr), (w - rr, rr), (rr, h - rr), (w - rr, h - rr)):
        cv2.circle(mask, (px, py), rr, 1, -1, cv2.LINE_AA)
    card[..., 3] = cv2.GaussianBlur(mask, (0, 0), 1)
    yoff = math.sin(t * 1.3) * 10
    M = np.float32([[s, 0, cx - w * s / 2], [0, s, cy - h * s / 2 + yoff]])
    shadow = card.copy()
    shadow[..., :3] = 0
    shadow[..., 3] = cv2.GaussianBlur(card[..., 3], (0, 0), 12) * 0.55
    _over(dst, shadow, M + np.float32([[0, 0, 14], [0, 0, 22]]))
    _over(dst, card, M)


# ----------------------------------------------------------------------------- captions
@lru_cache(maxsize=256)
def _caption_img(text, accent, active_words):
    import skia
    from animation.draw import font, text_width
    fnt = font("Poppins-Bold", 54)
    tw = text_width(text, fnt)
    surf = skia.Surface(int(tw + 80), 110)
    c = surf.getCanvas()
    c.clear(skia.ColorTRANSPARENT)
    p = skia.Paint(AntiAlias=True, Color=skia.Color(0, 0, 0, 90))
    c.drawRRect(skia.RRect.MakeRectXY(skia.Rect.MakeXYWH(4, 8, tw + 72, 92), 26, 26), p)
    x = 40
    sp = text_width(" ", fnt)
    for i, w_ in enumerate(text.split(" ")):
        st = skia.Paint(AntiAlias=True, Style=skia.Paint.kStroke_Style, StrokeWidth=9, Color=skia.Color(18, 10, 24))
        st.setStrokeJoin(skia.Paint.kRound_Join)
        c.drawString(w_, x, 72, fnt, st)
        col = accent if i < active_words else (255, 255, 255)
        c.drawString(w_, x, 72, fnt, skia.Paint(AntiAlias=True, Color=skia.Color(*col)))
        x += text_width(w_, fnt) + sp
    arr = surf.makeImageSnapshot().toarray(colorType=skia.kRGBA_8888_ColorType).astype(np.float32) / 255
    return arr


def caption_chunks(text, t0, t1, max_chars=22):
    words = text.split()
    chunks, cur = [], []
    for w_ in words:
        if cur and len(" ".join(cur + [w_])) > max_chars:
            chunks.append(cur)
            cur = []
        cur.append(w_)
    if cur:
        if chunks and len(" ".join(cur)) <= 8 and len(" ".join(chunks[-1] + cur)) <= max_chars + 4:
            chunks[-1] += cur
        else:
            chunks.append(cur)
    tot = sum(len(" ".join(c)) + 1 for c in chunks)
    out, t = [], t0
    for c in chunks:
        d = (t1 - t0) * (len(" ".join(c)) + 1) / tot
        out.append((t, t + d, c))
        t += d
    return out


def _draw_caption(dst, cap_list, t):
    for (c0, c1, words, accent) in cap_list:
        if c0 - 0.02 <= t < c1 + (0.25 if c1 == cap_list[-1][1] else 0):
            text = " ".join(words)
            n = len(words)
            frac = np.clip((t - c0) / max(c1 - c0, 1e-3), 0, 1)
            active = min(n, int(frac * n) + 1)
            img = _caption_img(text, accent, active)
            h, w = img.shape[:2]
            x, y = (W - w) // 2, 1405
            sub = dst[y:y + h, x:x + w]
            a = img[..., 3:4]
            sub[:] = sub * (1 - a) + img[..., :3] * a
            return


def _draw_text_block(dst, lines, y, size, color=(1, 0.96, 0.85), fontname="Kalam-Bold", alpha=1.0):
    import skia
    from animation.draw import draw_text_centered, font
    surf = skia.Surface(W, 200 * len(lines) + 60)
    c = surf.getCanvas()
    c.clear(skia.ColorTRANSPARENT)
    f = font(fontname, size)
    for i, ln in enumerate(lines):
        draw_text_centered(c, ln, W / 2, size + 10 + i * size * 1.3, f,
                           "#%02x%02x%02x" % tuple(int(v * 255) for v in color), 1.0, outline="#1a1030", outline_w=7)
    img = surf.makeImageSnapshot().toarray(colorType=skia.kRGBA_8888_ColorType).astype(np.float32) / 255
    h = img.shape[0]
    sub = dst[y:y + h]
    a = img[..., 3:4] * alpha
    sub[:] = sub * (1 - a) + img[..., :3] * a


# ----------------------------------------------------------------------------- the renderer
class PilotRenderer:
    def __init__(self, plan):
        from .assets import load
        from .puppet import PaintedActor
        self.plan = plan
        self.girl = PaintedActor(*load("girl_portrait", OUTFIT), kind="girl", seed=0.7)
        self.mahadev = PaintedActor(*load("mahadev_portrait"), kind="mahadev", seed=2.1)
        self.extra = {}
        for name, kind in (("girl_happy_closed", "girl"), ("girl_surprised", "girl"),
                           ("girl_full_front", "girl"), ("mahadev_full_front", "mahadev")):
            self.extra[name] = PaintedActor(*load(name, OUTFIT), kind=kind, seed=len(name) * 0.37, hair_amp=0.6)
        self.details = {n: load(n)[0].astype(np.float32) / 255 for n in ("detail_moon",)}
        self.env = plan["mouth_env"]
        self.blinks = plan["blinks"]
        self.bgs = {}

    def bg(self, blur, warm=0.0, night=0.0):
        k = (blur, warm, night)
        if k not in self.bgs:
            self.bgs[k] = _bg_plate(blur, warm, night)
        return self.bgs[k]

    def mouth(self, who, t):
        e = self.env[who]
        i = int(t * 30)
        return float(e[i]) if 0 <= i < len(e) else 0.0

    def blink(self, who, t):
        for bt in self.blinks[who]:
            if bt <= t <= bt + 0.17:
                return 1.0 - abs((t - bt - 0.085) / 0.085) * 0.6
        return 0.0

    def actor_frame(self, actor, who, t, speaking):
        m = self.mouth(who, t) if speaking else 0.0
        return actor.frame(t, mouth_open=m, blink=self.blink(who, t))

    def render(self, shot, t):
        k = (t - shot["t0"]) / max(shot["t1"] - shot["t0"], 1e-3)
        ez = 0.5 - 0.5 * math.cos(math.pi * min(1, max(0, k)))
        z0, z1 = shot.get("zoom", (1.0, 1.04))
        zoom = z0 + (z1 - z0) * ez
        kind = shot["kind"]
        frame = None
        if kind in ("girl_medium", "girl_close"):
            frame = self.bg(16 if kind == "girl_medium" else 24, warm=0.6).copy()
            _glow(frame, W * 0.75, H * 0.25, 900, (1.0, 0.75, 0.5), 0.18)
            img = self.actor_frame(self.girl, "girl", t, shot.get("speaking") == "girl")
            ih, iw = img.shape[:2]
            if kind == "girl_medium":
                M = _place(iw, ih, W * 0.5, H * 0.6, H * 1.0, zoom, focus=(0.47, 0.55))
            else:
                M = _place(iw, ih, W * 0.5, H * 0.43, H * 1.55, zoom, focus=(0.47, 0.42))
            _over(frame, img, M)
            _particles(frame, t, n=35, strength=0.45, rise=25)
        elif kind in ("girl_dream", "girl_react"):
            frame = self.bg(26, warm=0.8 if kind == "girl_dream" else 0.3).copy()
            act = self.extra[shot["asset"]]
            img = act.frame(t, blink=0.0)
            ih, iw = img.shape[:2]
            if kind == "girl_dream":
                _glow(frame, W / 2, H * 0.45, 800, (1.0, 0.8, 0.6), 0.35)
            M = _place(iw, ih, W * 0.5, H * 0.56, H * 1.0, zoom * (1 + 0.05 * ez), focus=(0.5, 0.5))
            _over(frame, img, M)
            _particles(frame, t, n=60 if kind == "girl_dream" else 30, strength=0.6, rise=35)
        elif kind == "cutaway":
            frame = self.bg(30, warm=0.4, night=0.6).copy()
            _glow(frame, W / 2, H * 0.42, 700, (1.0, 0.92, 0.7), 0.5)
            _panel(frame, self.details[shot["asset"]], t - shot["t0"], W / 2, H * 0.42, 700)
            _particles(frame, t, n=70, strength=0.75, rise=45)
        elif kind in ("mahadev_medium", "mahadev_close", "mahadev_appear"):
            frame = self.bg(18 if kind != "mahadev_close" else 26, night=0.55).copy()
            appear = 1.0
            if kind == "mahadev_appear":
                appear = min(1, max(0, (t - shot["t0"]) / 1.1))
                appear = appear * appear * (3 - 2 * appear)
            _glow(frame, W * 0.55, H * 0.36, 1100, (0.85, 0.9, 1.0), 0.35 * appear)
            _glow(frame, W * 0.55, H * 0.36, 520, (1.0, 0.9, 0.65), 0.3 * appear)
            img = self.actor_frame(self.mahadev, "mahadev", t, shot.get("speaking") == "mahadev")
            ih, iw = img.shape[:2]
            if kind == "mahadev_close":
                M = _place(iw, ih, W * 0.52, H * 0.42, H * 1.45, zoom, focus=(0.6, 0.47))
            else:
                M = _place(iw, ih, W * 0.48, H * 0.6, H * 1.0, zoom * (0.97 + 0.03 * appear), focus=(0.55, 0.52))
            _over(frame, img, M, alpha_mul=appear)
            _particles(frame, t, n=70, seed=9, color=(1.0, 0.9, 0.65), strength=0.8 * (0.6 + 0.4 * appear), rise=55)
            if kind == "mahadev_appear":
                flash = math.sin(math.pi * min(1, (t - shot["t0"]) / 0.9))
                frame[:] = np.clip(frame + flash * 0.55 * np.array([1, 0.95, 0.85], np.float32), 0, 1)
        elif kind in ("wide_girl", "two_shot_wide"):
            frame = self.bg(shot.get("bg_blur", 4), warm=0.5, night=0.2 if kind == "wide_girl" else 0.35).copy()
            g = self.extra["girl_full_front"].frame(t)
            gh, gw = g.shape[:2]
            if kind == "wide_girl":
                _over(frame, g, _place(gw, gh, W * 0.5, H * 0.66, H * 0.42, zoom, focus=(0.5, 0.5)))
            else:
                m = self.extra["mahadev_full_front"].frame(t)
                mh, mw = m.shape[:2]
                _glow(frame, W * 0.64, H * 0.55, 600, (1.0, 0.88, 0.6), 0.35)
                _over(frame, m, _place(mw, mh, W * 0.64, H * 0.63, H * 0.53, zoom, focus=(0.5, 0.5)))
                _over(frame, g, _place(gw, gh, W * 0.36, H * 0.665, H * 0.46, zoom, focus=(0.5, 0.5)))
            _particles(frame, t, n=40, strength=0.5, rise=20)
        elif kind == "end_card":
            frame = self.bg(34, night=0.85).copy()
            _glow(frame, W / 2, H * 0.4, 900, (1.0, 0.85, 0.55), 0.35)
            _particles(frame, t, n=90, strength=0.8, rise=35)
            lt = t - shot["t0"]
            a1 = min(1, max(0, lt / 0.8))
            _draw_text_block(frame, ["Jo bhi meri pooja karega,", "use pariksha to deni hogi."], 640, 74, alpha=a1)
            a2 = min(1, max(0, (lt - 1.0) / 0.8))
            _draw_text_block(frame, ["Mahadev & Me"], 1050, 64, color=(1.0, 0.83, 0.42), fontname="YatraOne-Regular", alpha=a2)
        _vignette(frame)
        if shot.get("title") and t < 3.2:
            a = min(1, t / 0.4) * (1 - max(0, (t - 2.6) / 0.6))
            _draw_text_block(frame, ["MAHADEV & ME"], 230, 72, color=(1.0, 0.83, 0.42), fontname="YatraOne-Regular", alpha=a)
            _draw_text_block(frame, ["Pilot"], 340, 46, color=(1, 1, 1), fontname="Kalam-Bold", alpha=a)
        if shot.get("fade_out") and t > shot["t1"] - shot["fade_out"]:
            frame *= 1 - (t - (shot["t1"] - shot["fade_out"])) / shot["fade_out"]
        _draw_caption(frame, self.plan["captions"], t)
        return frame


def _render_shot(args):
    plan, idx, w, h, fps, out = args
    R = PilotRenderer(plan)
    shot = plan["shots"][idx]
    prev = plan["shots"][idx - 1] if idx > 0 else None
    f0, f1 = round(shot["t0"] * fps), round(shot["t1"] * fps)
    cmd = ["ffmpeg", "-y", "-v", "error", "-f", "rawvideo", "-pix_fmt", "rgb24", "-s", f"{w}x{h}", "-r", str(fps),
           "-i", "-", "-c:v", "libx264", "-preset", "medium", "-crf", "18", "-pix_fmt", "yuv420p", str(out)]
    p = subprocess.Popen(cmd, stdin=subprocess.PIPE)
    t_start = time.time()
    for f in range(f0, f1):
        t = f / fps
        fr = R.render(shot, t)
        # swoosh: quick whip-pan blend from the previous shot (first 0.3 s) – like the reference's transitions
        if prev is not None and shot.get("transition") != "glow" and t - shot["t0"] < 0.3 and shot["kind"] != "end_card":
            k = min(1.0, max(0.0, (t - shot["t0"]) / 0.3))
            pf = R.render(prev, shot["t0"] - 0.001)
            off = int((1 - k) * W * 0.18)
            mix_ = np.roll(fr, off, axis=1) * k + np.roll(pf, -int(k * W * 0.18), axis=1) * (1 - k)
            fr = cv2.blur(mix_, (int(41 * (1 - abs(2 * k - 1))) + 1, 1))
        if w != W:
            fr = cv2.resize(fr, (w, h), interpolation=cv2.INTER_AREA)
        p.stdin.write((np.clip(fr, 0, 1) * 255 + 0.5).astype(np.uint8).tobytes())
    p.stdin.close()
    p.wait()
    return shot["id"], f1 - f0, time.time() - t_start


def mouth_envelope(x, fps=30, gate_db=-38):
    """Frame-rate mouth openness from the voice: RMS -> dB -> 0..1, fast attack, slower release."""
    hop = SR // fps
    n = max(1, len(x) // hop)
    rms = np.array([np.sqrt(np.mean(x[i * hop:(i + 1) * hop] ** 2) + 1e-12) for i in range(n)])
    db = 20 * np.log10(rms + 1e-9)
    ref = np.percentile(db[db > gate_db], 90) if np.any(db > gate_db) else -20
    o = np.clip((db - gate_db) / (ref - gate_db + 1e-6), 0, 1) ** 1.1
    out = np.zeros_like(o)
    v = 0.0
    for i, oi in enumerate(o):
        v = v + (oi - v) * (0.75 if oi > v else 0.45)
        out[i] = v
    # add a little syllable flutter so long vowels don't freeze open
    out *= 0.85 + 0.15 * np.sin(np.arange(n) * 1.9)
    return np.nan_to_num(out, nan=0.0)


def build(preview=False, jobs=4, log=print):
    OUTDIR.mkdir(parents=True, exist_ok=True)
    CACHE.mkdir(parents=True, exist_ok=True)
    log("[1/5] audio: clean girl VO, isolate Mahadev voice")
    girl, girl_spans, mvo = prepare_audio(log)
    shots, (m0, m1) = shot_plan(girl_spans, len(girl) / SR, len(mvo) / SR)
    total = shots[-1]["t1"]
    n = int(total * SR) + SR
    g_track = np.zeros(n, np.float32)
    g_track[int(GIRL_START * SR):int(GIRL_START * SR) + len(girl)] = girl
    m_track = np.zeros(n, np.float32)
    m_track[int(m0 * SR):int(m0 * SR) + len(mvo)] = mvo
    fps = 24 if preview else 30
    env = {"girl": mouth_envelope(g_track, 30).tolist(), "mahadev": mouth_envelope(m_track, 30).tolist()}
    caps = []
    for (a, b), text in zip(girl_spans, CAPTIONS_GIRL):
        caps += [(c0, c1, tuple(w), (255, 183, 207)) for c0, c1, w in caption_chunks(text, a, b)]
    caps += [(c0, c1, tuple(w), (255, 211, 107)) for c0, c1, w in caption_chunks(CAPTION_MAHADEV, m0, m1)]
    rng = random.Random(5)
    blinks = {"girl": [], "mahadev": []}
    for who in blinks:
        tt = rng.uniform(0.8, 1.6)
        while tt < total:
            blinks[who].append(round(tt, 2))
            tt += rng.uniform(2.4, 4.6)
    plan = dict(shots=shots, mouth_env=env, captions=caps, blinks=blinks, total=total)
    (OUTDIR / "plan.json").write_text(json.dumps({k: v for k, v in plan.items() if k != "mouth_env"}, indent=1, default=list))
    log("[2/5] music + mix")
    from audio.mix import mix
    st = mix(g_track + m_track, total, "dream", ambient=[("rooftop_wind", 0.0, total)],
             sfx_events=[("divine_shimmer", shots[6]["t0"]), ("soft_whoosh", shots[11]["t0"]), ("bloom_chime", shots[2]["t0"])],
             swell_at=m0, music_gain_db=-2.0, stems_out=str(CACHE / "stem"))
    mixwav = CACHE / "mix.wav"
    sf.write(mixwav, st, SR, subtype="PCM_24")
    log("[3/5] assets (sheet art: upscale x4 anime + cut-out + outfit recolour)")
    from .assets import build_all
    build_all(OUTFIT, log=log)
    log(f"[4/5] render {len(shots)} shots ({'preview 540x960@24' if preview else 'final 1080x1920@30'})")
    w, h = (540, 960) if preview else (W, H)
    segs = []
    tasks = []
    for i, s in enumerate(shots):
        seg = CACHE / f"seg_{s['id']}_{w}.mp4"
        segs.append(seg)
        tasks.append((plan, i, w, h, fps, seg))
    with ProcessPoolExecutor(max_workers=jobs) as ex:
        for sid, nf, dt in ex.map(_render_shot, tasks):
            log(f"      {sid}: {nf} frames in {dt:.1f}s")
    log("[5/5] assemble")
    lst = CACHE / "segs.txt"
    lst.write_text("".join(f"file '{s}'\n" for s in segs))
    vid = CACHE / "video.mp4"
    subprocess.run(["ffmpeg", "-y", "-v", "error", "-f", "concat", "-safe", "0", "-i", str(lst), "-c", "copy", str(vid)], check=True)
    final = OUTDIR / ("pilot_v2_preview.mp4" if preview else "pilot_v2.mp4")
    subprocess.run(["ffmpeg", "-y", "-v", "error", "-i", str(vid), "-i", str(mixwav), "-map", "0:v", "-map", "1:a",
                    "-c:v", "copy", "-af", "loudnorm=I=-14:TP=-1.5:LRA=11", "-c:a", "aac", "-b:a", "192k", "-ar", "48000",
                    "-movflags", "+faststart", "-t", f"{total:.3f}", str(final)], check=True)
    # subtitles
    def ts(x):
        hh, r = divmod(x, 3600)
        mm, ss = divmod(r, 60)
        return f"{int(hh):02d}:{int(mm):02d}:{int(ss):02d},{int((ss - int(ss)) * 1000):03d}"
    srt = []
    for i, ((a, b), text) in enumerate(list(zip(girl_spans, CAPTIONS_GIRL)) + [((m0, m1), CAPTION_MAHADEV)], 1):
        srt.append(f"{i}\n{ts(a)} --> {ts(b)}\n{text}\n")
    (OUTDIR / "pilot_v2_hinglish.srt").write_text("\n".join(srt), encoding="utf-8")
    log(f"      -> {final}  ({total:.2f}s)")
    return final, plan


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--preview", action="store_true")
    ap.add_argument("--jobs", type=int, default=4)
    a = ap.parse_args()
    build(a.preview, a.jobs)


if __name__ == "__main__":
    main()
