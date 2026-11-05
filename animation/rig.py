"""Shared 2.5D puppet rig: pose state, expressions, visemes, face features, arm IK, hands.

Coordinates: body space origin = base of the neck, +y down, 1 unit = 1 px at scale 1.
Head space origin = centre of the face on the eye line.

"yaw" in [-1, 1]: +1 = character turned towards screen-right.
"pitch" in [-1, 1]: +1 = looking down.
"""
from __future__ import annotations

import math
from dataclasses import dataclass, field

import skia

from .draw import (capsule, clamp, ellipse, fill, lerp, linear, path_from, radial,
                   shade, stroke)

# ------------------------------------------------------------------ expressions
# brow: raise both | inner: inner-brow raise (sad/worried) | furrow: knit brows
# lid: eye openness multiplier | squint: lower-lid raise (smiling eyes)
# smile: mouth corners (-1 sad .. 1 big smile) | jaw: extra mouth opening bias
# closed_happy: eyes drawn as ^ ^ arcs | asym: one brow raised (curious)
EXPRESSIONS = {
    "neutral":       dict(brow=0.0, inner=0.0, furrow=0.0, lid=1.0, squint=0.05, smile=0.12, jaw=0.0),
    "smile":         dict(brow=0.1, inner=0.0, furrow=0.0, lid=0.95, squint=0.35, smile=0.75, jaw=0.0),
    "laugh":         dict(brow=0.25, inner=0.0, furrow=0.0, lid=0.7, squint=0.7, smile=1.0, jaw=0.45),
    "sad":           dict(brow=-0.05, inner=0.85, furrow=0.1, lid=0.82, squint=0.0, smile=-0.45, jaw=0.0),
    "disappointed":  dict(brow=-0.1, inner=0.55, furrow=0.0, lid=0.72, squint=0.0, smile=-0.32, jaw=0.0),
    "hurt":          dict(brow=0.0, inner=0.95, furrow=0.2, lid=0.85, squint=0.1, smile=-0.4, jaw=0.0, teary=1.0),
    "worried":       dict(brow=0.1, inner=0.9, furrow=0.35, lid=1.05, squint=0.0, smile=-0.22, jaw=0.0),
    "frustrated":    dict(brow=-0.2, inner=0.0, furrow=0.85, lid=0.92, squint=0.15, smile=-0.35, jaw=0.0),
    "surprised":     dict(brow=0.9, inner=0.2, furrow=0.0, lid=1.25, squint=0.0, smile=0.0, jaw=0.35),
    "thoughtful":    dict(brow=0.15, inner=0.1, furrow=0.2, lid=0.9, squint=0.1, smile=0.05, jaw=0.0, asym=0.5),
    "curious":       dict(brow=0.35, inner=0.1, furrow=0.0, lid=1.05, squint=0.0, smile=0.22, jaw=0.0, asym=0.45),
    "calm":          dict(brow=0.0, inner=0.05, furrow=0.0, lid=0.84, squint=0.15, smile=0.35, jaw=0.0),
    "compassionate": dict(brow=0.05, inner=0.4, furrow=0.0, lid=0.86, squint=0.25, smile=0.45, jaw=0.0),
    "playful":       dict(brow=0.3, inner=0.0, furrow=0.0, lid=0.9, squint=0.4, smile=0.7, jaw=0.0, asym=0.35),
    "peaceful":      dict(brow=0.05, inner=0.15, furrow=0.0, lid=0.0, squint=0.0, smile=0.55, jaw=0.0, closed_happy=1.0),
    "hopeful":       dict(brow=0.25, inner=0.25, furrow=0.0, lid=1.0, squint=0.2, smile=0.5, jaw=0.0),
    "focused":       dict(brow=-0.1, inner=0.0, furrow=0.45, lid=0.88, squint=0.15, smile=0.0, jaw=0.0),
}
_EXPR_KEYS = ("brow", "inner", "furrow", "lid", "squint", "smile", "jaw", "asym",
              "closed_happy", "teary")


def expr_params(name_or_mix):
    """'smile' or {'smile':0.6,'sad':0.4} -> param dict."""
    if isinstance(name_or_mix, str):
        name_or_mix = {name_or_mix: 1.0}
    out = {k: 0.0 for k in _EXPR_KEYS}
    tot = sum(name_or_mix.values()) or 1.0
    for name, w in name_or_mix.items():
        e = EXPRESSIONS.get(name, EXPRESSIONS["neutral"])
        for k in _EXPR_KEYS:
            out[k] += e.get(k, 0.0) * w / tot
    return out


def blend_params(a, b, t):
    return {k: lerp(a.get(k, 0.0), b.get(k, 0.0), t) for k in set(a) | set(b)}


# ------------------------------------------------------------------ visemes (Rhubarb shapes)
# open: 0..1, width: x-scale of mouth, round: lip rounding, teeth: upper teeth visibility,
# tongue: tongue visibility, bite: lower lip tucked under teeth (F/V)
VISEMES = {
    "X": dict(open=0.0, width=1.0, round=0.0, teeth=0.0, tongue=0.0, bite=0.0),
    "A": dict(open=0.0, width=0.95, round=0.0, teeth=0.0, tongue=0.0, bite=0.0),
    "B": dict(open=0.22, width=1.05, round=0.0, teeth=1.0, tongue=0.0, bite=0.0),
    "C": dict(open=0.48, width=1.05, round=0.0, teeth=0.7, tongue=0.2, bite=0.0),
    "D": dict(open=0.9, width=1.0, round=0.0, teeth=0.5, tongue=0.5, bite=0.0),
    "E": dict(open=0.55, width=0.78, round=0.55, teeth=0.2, tongue=0.2, bite=0.0),
    "F": dict(open=0.28, width=0.58, round=1.0, teeth=0.0, tongue=0.0, bite=0.0),
    "G": dict(open=0.16, width=0.95, round=0.0, teeth=1.0, tongue=0.0, bite=1.0),
    "H": dict(open=0.5, width=0.92, round=0.0, teeth=0.6, tongue=0.9, bite=0.0),
}


def viseme_params(v):
    return dict(VISEMES.get(v, VISEMES["X"]))


# ------------------------------------------------------------------ gestures
# Wrist target (body space) for the SCREEN-LEFT arm; screen-right arm mirrors x.
# hand: drawing style of the hand.  Values are fractions of the arm reach.
GESTURES = {
    # w: wrist target, hand: hand style, fs: forearm foreshortening (forearm pointing at camera)
    "rest":      dict(w=(-1.02, 1.55), hand="relaxed", fs=1.0),
    "lap":       dict(w=(-0.42, 1.60), hand="relaxed", fs=0.75),
    "explain":   dict(w=(-1.30, 0.95), hand="palm_up", fs=0.55),
    "abhaya":    dict(w=(-1.10, 0.10), hand="abhaya", fs=0.8),
    "heart":     dict(w=(0.12, 0.62), hand="flat", fs=0.9),
    "chin":      dict(w=(-0.35, -0.55), hand="fist", fs=1.0),
    "phone":     dict(w=(-0.30, 1.05), hand="phone", fs=0.6),
    "phone_up":  dict(w=(-0.25, 0.65), hand="phone", fs=0.6),
    "point_up":  dict(w=(-1.15, -0.35), hand="point", fs=0.9),
    "shrug":     dict(w=(-1.45, 0.95), hand="palm_up", fs=0.6),
    "reach":     dict(w=(-1.55, 0.65), hand="palm_out", fs=1.0),
    "pocket":    dict(w=(-0.85, 1.55), hand="relaxed", fs=0.9),
}


@dataclass
class Pose:
    t: float = 0.0
    yaw: float = 0.0
    pitch: float = 0.0
    roll: float = 0.0
    expr: dict = field(default_factory=lambda: expr_params("neutral"))
    blink: float = 0.0          # 0 open .. 1 closed
    look: tuple = (0.0, 0.0)    # pupil offset (-1..1)
    mouth: dict = field(default_factory=lambda: viseme_params("X"))
    arm_l: dict = field(default_factory=lambda: dict(GESTURES["rest"]))
    arm_r: dict = field(default_factory=lambda: dict(GESTURES["rest"]))
    breath: float = 0.0         # -1..1
    sway: float = 0.0           # hair sway -1..1
    view: str = "front"         # front | back
    light: str = "neutral"      # used for subtle rim light hints
    phone_glow: float = 0.0     # light from a phone screen on the face


def blend_gesture(a, b, t):
    w = (lerp(a["w"][0], b["w"][0], t), lerp(a["w"][1], b["w"][1], t))
    return dict(w=w, hand=b["hand"] if t > 0.5 else a["hand"],
                fs=lerp(a.get("fs", 1.0), b.get("fs", 1.0), t))


# ------------------------------------------------------------------ projection
class FaceProj:
    """Maps flat face coordinates onto a turned head (cheap cylindrical model)."""

    def __init__(self, yaw, pitch, R=100.0):
        self.phi = clamp(yaw, -1, 1) * 0.6
        self.pitch = clamp(pitch, -1, 1)
        self.R = R

    def x(self, x0, depth=1.0):
        th0 = math.asin(clamp(x0 / self.R, -0.999, 0.999))
        return self.R * math.sin(th0 + self.phi) + (depth - 1.0) * self.R * math.sin(self.phi)

    def sx(self, x0):
        th0 = math.asin(clamp(x0 / self.R, -0.999, 0.999))
        return max(0.15, math.cos(th0 + self.phi) / max(0.2, math.cos(th0)))

    def y(self, y0, depth=1.0):
        # looking down pushes features down and compresses the forehead a little
        return y0 + self.pitch * 16 * depth - self.pitch * 0.05 * (y0 + 40)


# ------------------------------------------------------------------ IK
def ik(S, T, L1, L2, outward):
    sx, sy = S
    tx, ty = T
    dx, dy = tx - sx, ty - sy
    d = clamp(math.hypot(dx, dy), abs(L1 - L2) + 1, L1 + L2 - 0.5)
    a = math.atan2(dy, dx)
    cos_e = clamp((L1 * L1 + d * d - L2 * L2) / (2 * L1 * d), -1, 1)
    best = None
    for sgn in (1, -1):
        ang = a + sgn * math.acos(cos_e)
        E = (sx + L1 * math.cos(ang), sy + L1 * math.sin(ang))
        score = E[0] * outward * 0.6 + E[1] * 1.0  # prefer downward, then outward elbows
        if best is None or score > best[0]:
            best = (score, E)
    E = best[1]
    ang2 = math.atan2(ty - E[1], tx - E[0])
    W = (E[0] + L2 * math.cos(ang2), E[1] + L2 * math.sin(ang2))
    return E, W


# ------------------------------------------------------------------ face features
def draw_eye(c, cx, cy, w, h, sxf, pose: Pose, style, side, P):
    """One almond eye. side=-1 screen-left, +1 screen-right."""
    e = pose.expr
    lid = clamp(e["lid"], 0, 1.35) * (1 - clamp(pose.blink))
    closed_happy = e.get("closed_happy", 0)
    w *= sxf
    if closed_happy > 0.5 or lid < 0.12:
        # closed eye: curve (down-curve when blinking, up-arc when happy)
        bend = -h * 0.55 if closed_happy > 0.5 else h * 0.18
        p = skia.Path()
        p.moveTo(cx - w / 2, cy)
        p.quadTo(cx, cy + bend, cx + w / 2, cy)
        c.drawPath(p, stroke(style["lash"], style["lash_w"]))
        if style.get("flick"):
            out = cx + side * w / 2 if side else cx + w / 2
            p2 = skia.Path()
            p2.moveTo(out, cy)
            p2.lineTo(out + side * w * 0.13, cy - h * 0.12)
            c.drawPath(p2, stroke(style["lash"], style["lash_w"] * 0.6))
        return
    squint = clamp(e.get("squint", 0))
    top = cy - h * 0.62 * lid
    bot = cy + h * 0.42 * (1 - 0.55 * squint)
    tilt = style.get("tilt", 0.0) * side  # outer corner lift
    inner_x, outer_x = cx - side * w / 2, cx + side * w / 2
    lx, rx = min(inner_x, outer_x), max(inner_x, outer_x)
    ly = cy + (-tilt if lx == outer_x else 0)
    ry = cy + (-tilt if rx == outer_x else 0)
    shape = skia.Path()
    shape.moveTo(lx, ly)
    shape.cubicTo(lx + w * 0.22, top, rx - w * 0.28, top, rx, ry)
    shape.cubicTo(rx - w * 0.25, bot, lx + w * 0.25, bot, lx, ly)
    shape.close()
    c.drawPath(shape, fill(style["sclera"]))
    c.save()
    c.clipPath(shape, doAntiAlias=True)
    lxo, lyo = pose.look
    ir = h * style.get("iris", 0.5)
    ix, iy = cx + lxo * w * 0.22, cy + lyo * h * 0.22 - h * 0.04
    c.drawCircle(ix, iy, ir, fill(style["iris_col"], shader=radial(
        (ix, iy - ir * 0.3), ir * 1.2, [shade(style["iris_col"], 0.25), style["iris_col"],
                                         shade(style["iris_col"], -0.45)], [0, 0.55, 1])))
    c.drawCircle(ix, iy, ir, stroke(shade(style["iris_col"], -0.6), max(1.0, ir * 0.12)))
    c.drawCircle(ix, iy, ir * 0.45, fill("#140b08"))
    c.drawCircle(ix - ir * 0.35, iy - ir * 0.38, ir * 0.26, fill("#ffffff", 0.95))
    c.drawCircle(ix + ir * 0.32, iy + ir * 0.3, ir * 0.12, fill("#ffffff", 0.6))
    # upper-lid shadow
    c.drawPath(shape, stroke(shade(style["skin"], -0.35), h * 0.35, alpha=0.25, blur=h * 0.12))
    if e.get("teary", 0) > 0:
        c.drawPath(path_from([(lx + w * 0.15, bot - h * 0.12), (cx, bot - h * 0.02),
                              (rx - w * 0.15, bot - h * 0.12)], closed=False),
                   stroke("#dff3ff", h * 0.14, alpha=0.55 * e["teary"]))
    c.restore()
    # lash line (upper) – thicker towards the outer corner
    up = skia.Path()
    up.moveTo(lx, ly)
    up.cubicTo(lx + w * 0.22, top, rx - w * 0.28, top, rx, ry)
    c.drawPath(up, stroke(style["lash"], style["lash_w"]))
    if style.get("flick"):
        fl = skia.Path()
        ox, oy = (rx, ry) if side > 0 else (lx, ly)
        fl.moveTo(ox - side * w * 0.05, oy - h * 0.05)
        fl.quadTo(ox + side * w * 0.10, oy - h * 0.12, ox + side * w * 0.17, oy - h * 0.28)
        c.drawPath(fl, stroke(style["lash"], style["lash_w"] * 0.7))
    lo = skia.Path()
    lo.moveTo(lx + w * 0.12, ly + h * 0.08)
    lo.cubicTo(lx + w * 0.3, bot, rx - w * 0.3, bot, rx - w * 0.06, ry + h * 0.05)
    c.drawPath(lo, stroke(shade(style["lash"], 0.25), style["lash_w"] * 0.35, alpha=0.55))
    # crease
    cr = skia.Path()
    cr.moveTo(lx + w * 0.12, top - h * 0.12)
    cr.quadTo(cx, top - h * 0.38 * max(lid, 0.4), rx - w * 0.08, top - h * 0.05)
    c.drawPath(cr, stroke(shade(style["skin"], -0.3), max(1, style["lash_w"] * 0.3), alpha=0.5))


def draw_brow(c, cx, cy, w, side, pose: Pose, style, sxf):
    e = pose.expr
    raise_ = e["brow"] * 14 + (e.get("asym", 0) * 12 if side > 0 else 0)
    inner = e["inner"] * 12
    furrow = e["furrow"] * 7
    w *= sxf
    ix = cx - side * w / 2 + side * furrow * 0.6
    ox = cx + side * w / 2
    iy = cy - raise_ - inner + furrow * 0.9
    oy = cy - raise_ * 0.8 + inner * 0.35 + 4
    peak = (cx + side * w * 0.12, cy - raise_ - 9 - inner * 0.3)
    th = style["brow_w"]
    p = skia.Path()
    p.moveTo(ix, iy + th * 0.15)
    p.quadTo(peak[0], peak[1] - th * 0.55, ox, oy)
    p.quadTo(peak[0], peak[1] + th * 0.5, ix, iy + th * 0.9)
    p.close()
    c.drawPath(p, fill(style["brow"]))


def draw_mouth(c, mx, my, base_w, pose: Pose, style, sxf):
    m = pose.mouth
    e = pose.expr
    smile = e["smile"]
    open_ = clamp(m["open"] + e.get("jaw", 0) * (1 - m["open"]), 0, 1)
    width = base_w * m["width"] * (1 + 0.12 * max(smile, 0)) * sxf
    rnd = m["round"]
    hw = width / 2
    corner_y = my - smile * 9
    oh = open_ * style["mouth_h"] * (1 + 0.3 * rnd)
    lip = style["lip"]
    if oh < 2.5:
        p = skia.Path()
        p.moveTo(mx - hw, corner_y)
        p.cubicTo(mx - hw * 0.4, my + smile * 6 + 1, mx + hw * 0.4, my + smile * 6 + 1, mx + hw, corner_y)
        c.drawPath(p, stroke(style["mouth_line"], style["mouth_line_w"]))
        if style.get("lower_lip", True):
            ll = skia.Path()
            ll.moveTo(mx - hw * 0.55, my + 6 + smile * 3)
            ll.quadTo(mx, my + 14 + smile * 3, mx + hw * 0.55, my + 6 + smile * 3)
            c.drawPath(ll, stroke(lip, style["mouth_line_w"] * 1.5, alpha=0.35, blur=1.5))
        if smile > 0.25:  # dimple-ish corners
            for s in (-1, 1):
                d = skia.Path()
                d.moveTo(mx + s * hw * 1.02, corner_y - 3)
                d.quadTo(mx + s * hw * 1.12, corner_y + 1, mx + s * hw * 1.04, corner_y + 5)
                c.drawPath(d, stroke(style["mouth_line"], 1.6, alpha=0.5 * smile))
        return
    top_y = my - oh * 0.28
    bot_y = my + oh * 0.85
    outer = skia.Path()
    outer.moveTo(mx - hw, corner_y)
    outer.cubicTo(mx - hw * 0.5, top_y - 2, mx + hw * 0.5, top_y - 2, mx + hw, corner_y)
    outer.cubicTo(mx + hw * (0.9 - 0.3 * rnd), bot_y, mx - hw * (0.9 - 0.3 * rnd), bot_y, mx - hw, corner_y)
    outer.close()
    c.drawPath(outer, fill(style["mouth_in"]))
    c.save()
    c.clipPath(outer, doAntiAlias=True)
    if m["teeth"] > 0:
        c.drawRect(skia.Rect.MakeLTRB(mx - hw, top_y - 4, mx + hw, top_y + oh * 0.28 * m["teeth"] + 2),
                   fill("#f7f3ee"))
    if m.get("tongue", 0) > 0:
        c.drawPath(ellipse(mx, bot_y - oh * 0.1, hw * 0.55, oh * 0.32 * m["tongue"] + 2),
                   fill(style.get("tongue", "#d9737a")))
    c.restore()
    c.drawPath(outer, stroke(style["mouth_line"], style["mouth_line_w"] * 0.8, alpha=0.9))
    # lips
    ul = skia.Path()
    ul.moveTo(mx - hw, corner_y)
    ul.cubicTo(mx - hw * 0.5, top_y - 6, mx + hw * 0.5, top_y - 6, mx + hw, corner_y)
    c.drawPath(ul, stroke(lip, style["mouth_line_w"] * 1.6, alpha=0.6))
    ll = skia.Path()
    ll.moveTo(mx - hw * 0.8, corner_y + 3)
    ll.cubicTo(mx - hw * 0.4, bot_y + 6, mx + hw * 0.4, bot_y + 6, mx + hw * 0.8, corner_y + 3)
    c.drawPath(ll, stroke(lip, style["mouth_line_w"] * 2.4, alpha=0.65))
    if m.get("bite", 0) > 0.5:
        c.drawPath(ellipse(mx, my + 2, hw * 0.75, 4), fill(lip, 0.9))


def draw_nose(c, nx, ny, style, P: FaceProj):
    s = math.sin(P.phi)
    sh = shade(style["skin"], -0.28)
    # bridge shadow on the far side when turned
    if abs(s) > 0.05:
        br = skia.Path()
        br.moveTo(nx - s * 10, ny - 50)
        br.quadTo(nx - s * 4 + s * 6, ny - 15, nx + s * 6, ny)
        c.drawPath(br, stroke(sh, 4, alpha=0.35 * abs(s) * 2, blur=2))
    w = style.get("nose_w", 13)
    p = skia.Path()
    p.moveTo(nx - w * 0.55, ny + 4)
    p.quadTo(nx + s * 5, ny + 9, nx + w * 0.55, ny + 4)
    c.drawPath(p, stroke(shade(style["skin"], -0.38), 2.4, alpha=0.6))
    # nostril shadows + soft tip highlight
    for sd in (-1, 1):
        c.drawPath(ellipse(nx + sd * w * 0.5 + s * 3, ny + 2, 3.2, 2.2), fill(shade(style["skin"], -0.45), 0.45, blur=1))
    c.drawPath(ellipse(nx + s * 5, ny - 6, w * 0.6, 6), fill("#ffffff", 0.12, blur=3))


def draw_hand(c, W, ang, kind, skin, size, side, outline=None):
    """W wrist position, ang = forearm direction (radians), side: -1 screen-left arm."""
    ol = outline or shade(skin, -0.35)
    sk = fill(skin)
    st = stroke(ol, 2.2, alpha=0.8)
    c.save()
    c.translate(*W)
    if kind in ("abhaya", "palm_out"):
        # palm facing viewer, fingers up
        c.rotate(-8 * side if kind == "abhaya" else 70 * side)
        palm = skia.RRect.MakeRectXY(skia.Rect.MakeLTRB(-size * 0.42, -size * 0.85, size * 0.42, size * 0.05),
                                     size * 0.25, size * 0.25)
        for i, (fx, fl) in enumerate([(-0.3, 0.62), (-0.1, 0.72), (0.1, 0.7), (0.29, 0.58)]):
            fp = capsule((fx * size, -size * 0.75), (fx * size * 1.05, -size * (0.75 + fl)), size * 0.2, size * 0.17)
            c.drawPath(fp, sk)
            c.drawPath(fp, st)
        th = capsule((-side * size * 0.38, -size * 0.25), (-side * size * 0.72, -size * 0.62), size * 0.22, size * 0.17)
        c.drawPath(th, sk)
        c.drawPath(th, st)
        c.drawRRect(palm, sk)
        c.drawRRect(palm, st)
        crease = skia.Path()
        crease.moveTo(-size * 0.25, -size * 0.45)
        crease.quadTo(0, -size * 0.32, size * 0.25, -size * 0.5)
        c.drawPath(crease, stroke(ol, 1.6, alpha=0.4))
        c.restore()
        return
    c.rotate(math.degrees(ang))
    if kind == "fist":
        c.drawPath(ellipse(size * 0.42, 0, size * 0.45, size * 0.38), sk)
        c.drawPath(ellipse(size * 0.42, 0, size * 0.45, size * 0.38), st)
        for k in (-0.15, 0.05, 0.25):
            c.drawLine(size * 0.62, size * k, size * 0.82, size * k, stroke(ol, 1.5, alpha=0.5))
    elif kind == "point":
        c.drawPath(ellipse(size * 0.38, 0, size * 0.4, size * 0.34), sk)
        f = capsule((size * 0.6, -size * 0.1), (size * 1.25, -size * 0.12), size * 0.2, size * 0.17)
        c.drawPath(f, sk)
        c.drawPath(f, st)
        c.drawPath(ellipse(size * 0.38, 0, size * 0.4, size * 0.34), st)
    elif kind in ("palm_up", "flat"):
        hp = path_from([(0, -size * 0.28), (size * 0.6, -size * 0.36), (size * 1.05, -size * 0.2),
                        (size * 1.1, size * 0.08), (size * 0.6, size * 0.3), (0, size * 0.26)])
        c.drawPath(hp, sk)
        c.drawPath(hp, st)
        th = capsule((size * 0.3, -side * size * 0.25), (size * 0.75, -side * size * 0.5), size * 0.2, size * 0.15)
        c.drawPath(th, sk)
        c.drawPath(th, st)
        for k in (-0.12, 0.0, 0.12):
            c.drawLine(size * 0.75, size * k, size * 1.0, size * k * 1.1, stroke(ol, 1.3, alpha=0.4))
    else:  # relaxed / phone
        hp = path_from([(0, -size * 0.27), (size * 0.55, -size * 0.33), (size * 0.95, -size * 0.15),
                        (size * 0.98, size * 0.12), (size * 0.55, size * 0.3), (0, size * 0.25)])
        c.drawPath(hp, sk)
        c.drawPath(hp, st)
        th = capsule((size * 0.25, -side * size * 0.22), (size * 0.6, -side * size * 0.36), size * 0.18, size * 0.14)
        c.drawPath(th, sk)
        c.drawPath(th, st)
    c.restore()


def soft_shadow_under(c, path, color, alpha=0.35, blur=10, dx=0, dy=6):
    c.save()
    c.translate(dx, dy)
    c.drawPath(path, fill(color, alpha, blur=blur))
    c.restore()


def face_outline(P: FaceProj, half_w=95, chin=118, crown=-135, jaw=0.72, cheek=1.0):
    """Face silhouette (no hair) shifted for yaw."""
    s = math.sin(P.phi)
    pts_r = [(0, crown), (half_w * 0.72, crown + 22), (half_w * 0.98, -70), (half_w * cheek, 0),
             (half_w * (0.5 + jaw * 0.6), 44), (half_w * jaw, chin - 30), (half_w * 0.3, chin - 5)]
    pts = []
    # right side (screen right)
    for (x, y) in pts_r:
        fy = clamp((y + 20) / 140)          # lower face moves more with yaw
        far = 1 - 0.18 * max(-s, 0) * clamp((y + 60) / 120)   # far cheek flattens
        pts.append((x * far + s * P.R * 0.85 * fy * 0.55 + s * 10 * (1 - fy), P.y(y, 0.4)))
    pts.append((s * P.R * 0.55, P.y(chin, 0.6)))
    for (x, y) in reversed(pts_r[1:]):
        fy = clamp((y + 20) / 140)
        far = 1 - 0.18 * max(s, 0) * clamp((y + 60) / 120)
        pts.append((-x * far + s * P.R * 0.85 * fy * 0.55 + s * 10 * (1 - fy), P.y(y, 0.4)))
    return path_from(pts, closed=True, tension=0.55)
