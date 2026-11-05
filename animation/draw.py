"""Small helper layer over skia-python: colours, paints, paths, easing, text."""
from __future__ import annotations

import math
from functools import lru_cache
from pathlib import Path

import skia

ROOT = Path(__file__).resolve().parent.parent
FONTS = ROOT / "assets" / "fonts"


# ---------------------------------------------------------------- maths
def clamp(x, lo=0.0, hi=1.0):
    return lo if x < lo else hi if x > hi else x


def lerp(a, b, t):
    return a + (b - a) * t


def smoothstep(t):
    t = clamp(t)
    return t * t * (3 - 2 * t)


def ease_in_out(t):
    t = clamp(t)
    return 0.5 - 0.5 * math.cos(math.pi * t)


def ease_out(t):
    t = clamp(t)
    return 1 - (1 - t) ** 3


def noise1(t, seed=0.0):
    """Cheap smooth pseudo-noise in [-1, 1] built from incommensurate sines."""
    return (math.sin(t * 1.13 + seed * 3.1) * 0.5
            + math.sin(t * 2.31 + seed * 7.7) * 0.3
            + math.sin(t * 0.47 + seed * 1.9) * 0.2)


# ---------------------------------------------------------------- colour
def hexrgb(h: str):
    h = h.lstrip("#")
    if len(h) == 3:
        h = "".join(ch * 2 for ch in h)
    return int(h[0:2], 16), int(h[2:4], 16), int(h[4:6], 16)


def col(h: str, a: float = 1.0) -> int:
    r, g, b = hexrgb(h)
    return skia.Color(r, g, b, int(clamp(a) * 255))


def mix(h1: str, h2: str, t: float) -> str:
    a, b = hexrgb(h1), hexrgb(h2)
    return "#%02x%02x%02x" % tuple(int(round(lerp(x, y, clamp(t)))) for x, y in zip(a, b))


def shade(h: str, f: float) -> str:
    """f<0 darkens towards black, f>0 lightens towards white."""
    return mix(h, "#000000", -f) if f < 0 else mix(h, "#ffffff", f)


# ---------------------------------------------------------------- paints
def fill(color, alpha=1.0, blur=0.0, shader=None, blend=None):
    p = skia.Paint(AntiAlias=True)
    p.setColor(col(color, alpha) if isinstance(color, str) else color)
    if shader is not None:
        p.setShader(shader)
        p.setAlphaf(alpha)
    if blur > 0:
        p.setMaskFilter(skia.MaskFilter.MakeBlur(skia.kNormal_BlurStyle, blur))
    if blend is not None:
        p.setBlendMode(blend)
    return p


def stroke(color, width, alpha=1.0, blur=0.0, cap="round"):
    p = skia.Paint(AntiAlias=True, Style=skia.Paint.kStroke_Style, StrokeWidth=width)
    p.setColor(col(color, alpha) if isinstance(color, str) else color)
    p.setStrokeCap(skia.Paint.kRound_Cap if cap == "round" else skia.Paint.kButt_Cap)
    p.setStrokeJoin(skia.Paint.kRound_Join)
    if blur > 0:
        p.setMaskFilter(skia.MaskFilter.MakeBlur(skia.kNormal_BlurStyle, blur))
    return p


def linear(p0, p1, colors, pos=None):
    cs = [col(c) if isinstance(c, str) else col(*c) for c in colors]
    return skia.GradientShader.MakeLinear([skia.Point(*p0), skia.Point(*p1)], cs, pos)


def radial(c, r, colors, pos=None):
    cs = [col(c_) if isinstance(c_, str) else col(*c_) for c_ in colors]
    return skia.GradientShader.MakeRadial(skia.Point(*c), max(r, 0.01), cs, pos)


# ---------------------------------------------------------------- paths
def path_from(points, closed=True, smooth=True, tension=0.5):
    """Catmull-Rom spline through points -> skia.Path."""
    p = skia.Path()
    n = len(points)
    if n < 2:
        return p
    p.moveTo(*points[0])
    if not smooth or n < 3:
        for pt in points[1:]:
            p.lineTo(*pt)
        if closed:
            p.close()
        return p
    pts = list(points)
    rng = range(n if closed else n - 1)
    for i in rng:
        p0 = pts[(i - 1) % n] if (closed or i > 0) else pts[i]
        p1 = pts[i]
        p2 = pts[(i + 1) % n]
        p3 = pts[(i + 2) % n] if (closed or i + 2 < n) else p2
        k = tension / 3 * 2
        c1 = (p1[0] + (p2[0] - p0[0]) * k / 2, p1[1] + (p2[1] - p0[1]) * k / 2)
        c2 = (p2[0] - (p3[0] - p1[0]) * k / 2, p2[1] - (p3[1] - p1[1]) * k / 2)
        p.cubicTo(*c1, *c2, *p2)
    if closed:
        p.close()
    return p


def ellipse(cx, cy, rx, ry):
    p = skia.Path()
    p.addOval(skia.Rect.MakeLTRB(cx - rx, cy - ry, cx + rx, cy + ry))
    return p


def capsule(a, b, wa, wb):
    """Tapered limb polygon from point a (width wa) to b (width wb), round ends."""
    ax, ay = a
    bx, by = b
    ang = math.atan2(by - ay, bx - ax)
    nx, ny = -math.sin(ang), math.cos(ang)
    p = skia.Path()
    p.moveTo(ax + nx * wa / 2, ay + ny * wa / 2)
    p.lineTo(bx + nx * wb / 2, by + ny * wb / 2)
    p.arcTo(skia.Rect.MakeLTRB(bx - wb / 2, by - wb / 2, bx + wb / 2, by + wb / 2),
            math.degrees(ang) + 90, -180, False)
    p.lineTo(ax - nx * wa / 2, ay - ny * wa / 2)
    p.arcTo(skia.Rect.MakeLTRB(ax - wa / 2, ay - wa / 2, ax + wa / 2, ay + wa / 2),
            math.degrees(ang) - 90, -180, False)
    p.close()
    return p


# ---------------------------------------------------------------- text
@lru_cache(maxsize=32)
def typeface(name: str):
    f = FONTS / f"{name}.ttf"
    if f.exists():
        return skia.Typeface.MakeFromFile(str(f))
    return skia.Typeface.MakeDefault()


def font(name="Poppins-SemiBold", size=48):
    f = skia.Font(typeface(name), size)
    f.setEdging(skia.Font.Edging.kAntiAlias)
    f.setSubpixel(True)
    return f


def text_width(txt, fnt):
    return fnt.measureText(txt)


def wrap(txt, fnt, max_w):
    words, lines, cur = txt.split(), [], ""
    for w in words:
        t = (cur + " " + w).strip()
        if text_width(t, fnt) <= max_w or not cur:
            cur = t
        else:
            lines.append(cur)
            cur = w
    if cur:
        lines.append(cur)
    return lines


def draw_text_centered(c, txt, cx, y, fnt, color="#ffffff", alpha=1.0, outline=None,
                       outline_w=8, shadow=True):
    """Centered text. Words are drawn individually (some fonts' space glyph has stray outline
    contours that show up as dots when stroked)."""
    w = text_width(txt, fnt)
    sp = text_width(" ", fnt)
    x = cx - w / 2
    for word in txt.split(" "):
        if word:
            if shadow:
                c.drawString(word, x + 3, y + 5, fnt, fill("#000000", 0.45 * alpha, blur=6))
            if outline:
                c.drawString(word, x, y, fnt, stroke(outline, outline_w, alpha))
            c.drawString(word, x, y, fnt, fill(color, alpha))
        x += text_width(word, fnt) + sp
    return w
