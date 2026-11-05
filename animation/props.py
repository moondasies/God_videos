"""Animated props and insert shots: phone feed, unanswered chat, blooming flowers, divine particles."""
from __future__ import annotations

import math
import random

import skia

from .draw import (capsule, clamp, ease_in_out, ease_out, ellipse, fill, font, linear,
                   path_from, radial, shade, smoothstep, stroke, text_width)

SKIN = "#f2c6a6"


def _phone_body(c, x, y, w, h):
    c.drawRRect(skia.RRect.MakeRectXY(skia.Rect.MakeXYWH(x - 8, y - 8, w + 16, h + 16), 70, 70), fill("#000000", 0.5, blur=30))
    c.drawRRect(skia.RRect.MakeRectXY(skia.Rect.MakeXYWH(x - 14, y - 14, w + 28, h + 28), 72, 72), fill("#15161b"))
    scr = skia.RRect.MakeRectXY(skia.Rect.MakeXYWH(x, y, w, h), 58, 58)
    return scr


def _heart(x, y, r):
    p = skia.Path()
    p.moveTo(x, y + r * 0.9)
    p.cubicTo(x - r * 1.6, y - r * 0.2, x - r * 0.6, y - r * 1.3, x, y - r * 0.4)
    p.cubicTo(x + r * 0.6, y - r * 1.3, x + r * 1.6, y - r * 0.2, x, y + r * 0.9)
    p.close()
    return p


def _thumb(c, x, y, ang=-30):
    c.save()
    c.translate(x, y)
    c.rotate(ang)
    th = capsule((0, 0), (0, 260), 110, 130)
    c.drawPath(th, fill(SKIN))
    c.drawPath(th, stroke(shade(SKIN, -0.35), 4, alpha=0.7))
    c.drawPath(ellipse(0, 40, 34, 46), fill("#f8dcc8", 0.9))
    c.drawPath(ellipse(0, 40, 34, 46), stroke(shade(SKIN, -0.25), 2.5, alpha=0.6))
    c.restore()


POSTS_DEFAULT = [
    ("Riya S.", "Promoted to Senior Analyst!", "#f6c76b", "Congratulations!!"),
    ("Aman K.", "Got my offer letter today", "#8fc3f2", "So proud"),
    ("Neha (college)", "Moved to my new flat in Bengaluru", "#f2a0b6", "Goals!"),
    ("Kabir", "Cleared CA final", "#a7e0b8", "Legend"),
    ("Sana", "First international trip", "#c5b3f2", "Wow"),
    ("Ishaan", "Started my own studio", "#f2c6a0", "Inspiring"),
]


def phone_feed(c, t, dur, posts=None, W=1080, H=1920):
    """Close-up of the phone: a social feed of other people's milestones scrolling by."""
    posts = posts or POSTS_DEFAULT
    pw, ph = 720, 1380
    x, y = (W - pw) / 2, 470
    scr = _phone_body(c, x, y, pw, ph)
    c.save()
    c.clipRRect(scr, doAntiAlias=True)
    c.drawRect(skia.Rect.MakeXYWH(x, y, pw, ph), fill("#f4f2f7"))
    # scroll with flick + settle motion
    k = t / max(dur, 0.1)
    scroll = 0.0
    for i in range(3):
        seg = clamp(k * 3 - i)
        scroll += ease_out(seg) * 470
    top = y + 170 - scroll
    fb = font("Poppins-SemiBold", 34)
    fr = font("Poppins-Regular", 30)
    for i, (name, txt, colr, comment) in enumerate(posts * 2):
        py = top + i * 470
        if py > y + ph or py < y - 470:
            continue
        c.drawRRect(skia.RRect.MakeRectXY(skia.Rect.MakeXYWH(x + 30, py, pw - 60, 440), 28, 28), fill("#ffffff"))
        c.drawCircle(x + 90, py + 60, 34, fill(colr))
        c.drawString(name, x + 140, py + 72, fb, fill("#222"))
        c.drawRRect(skia.RRect.MakeRectXY(skia.Rect.MakeXYWH(x + 60, py + 120, pw - 120, 190), 18, 18),
                    fill(colr, shader=linear((0, py + 120), (0, py + 310), [shade(colr, 0.35), colr])))
        # confetti on the card
        r = random.Random(i)
        for _ in range(14):
            c.drawCircle(x + 70 + r.random() * (pw - 140), py + 130 + r.random() * 170, r.uniform(3, 7),
                         fill(r.choice(["#ffffff", "#ff7a7a", "#ffd23f", "#6ad0ff"]), 0.85))
        c.drawString(txt, x + 60, py + 360, font("Poppins-SemiBold", 31), fill("#1d1d1f"))
        c.drawPath(_heart(x + 74, py + 398, 14), fill("#e0457b"))
        c.drawString(str(120 + i * 37) + " likes  ·  " + comment, x + 100, py + 410, fr, fill("#e0457b"))
    # status bar
    c.drawRect(skia.Rect.MakeXYWH(x, y, pw, 120), fill("#f4f2f7"))
    c.drawString("11:47 PM", x + 70, y + 80, font("Poppins-SemiBold", 30), fill("#111"))
    c.drawString("feed", x + pw / 2 - 30, y + 80, font("Poppins-Bold", 30), fill("#111"))
    c.restore()
    # thumb flicks upwards
    fl = (k * 3) % 1
    _thumb(c, x + pw - 120, y + ph - 260 - 160 * math.sin(math.pi * fl) * 0.6, -28)
    # phone screen light spill
    c.drawRect(skia.Rect.MakeXYWH(0, 0, W, H), fill("#9fc3ff", 0.05))


def phone_chat(c, t, dur, msg_lines, seen_time="6:42 PM", W=1080, H=1920):
    """Close-up of the phone: her long message, marked 'Seen', no reply. Typing dots appear & vanish."""
    pw, ph = 720, 1380
    x, y = (W - pw) / 2, 470
    scr = _phone_body(c, x, y, pw, ph)
    c.save()
    c.clipRRect(scr, doAntiAlias=True)
    c.drawRect(skia.Rect.MakeXYWH(x, y, pw, ph), fill("#efe7dc"))
    c.drawRect(skia.Rect.MakeXYWH(x, y, pw, 200), fill("#2f4a5a"))
    c.drawCircle(x + 100, y + 120, 42, fill("#d0a37a"))
    c.drawString("Priya", x + 165, y + 115, font("Poppins-SemiBold", 36), fill("#ffffff"))
    c.drawString("last seen today at " + seen_time, x + 165, y + 158, font("Poppins-Regular", 24), fill("#d6e3ea"))
    fr = font("Poppins-Regular", 32)
    by = y + 430
    lines = msg_lines
    bw = max(text_width(l, fr) for l in lines) + 60
    bh = 52 * len(lines) + 80
    bx = x + pw - 40 - bw
    pop = ease_out(clamp(t / 0.4))
    c.save()
    c.translate(bx + bw, by)
    c.scale(0.9 + 0.1 * pop, 0.9 + 0.1 * pop)
    c.translate(-(bx + bw), -by)
    c.drawRRect(skia.RRect.MakeRectXY(skia.Rect.MakeXYWH(bx, by, bw, bh), 26, 26), fill("#d4f5c4"))
    for i, l in enumerate(lines):
        c.drawString(l, bx + 30, by + 60 + i * 52, fr, fill("#1b1b1b"))
    c.drawString(seen_time, bx + bw - 190, by + bh - 20, font("Poppins-Regular", 24), fill("#5f6b62"))
    for k in range(2):
        tick = skia.Path()
        tick.moveTo(bx + bw - 76 + k * 14, by + bh - 32)
        tick.lineTo(bx + bw - 68 + k * 14, by + bh - 24)
        tick.lineTo(bx + bw - 54 + k * 14, by + bh - 42)
        c.drawPath(tick, stroke("#3b8fd9", 3))
    c.restore()
    # "Seen" label fades in
    sa = smoothstep((t - 0.8) / 0.5)
    c.drawString("Seen", bx + bw - 80, by + bh + 46, font("Poppins-SemiBold", 28), fill("#6b6b6b", sa))
    # typing dots appear… then vanish (the hurt beat)
    if 1.6 < t < 2.9:
        tx, ty = x + 60, by + bh + 120
        c.drawRRect(skia.RRect.MakeRectXY(skia.Rect.MakeXYWH(tx, ty, 140, 70), 30, 30), fill("#ffffff"))
        for k in range(3):
            a = 0.4 + 0.6 * (0.5 + 0.5 * math.sin(t * 8 - k))
            c.drawCircle(tx + 40 + k * 30, ty + 35, 9, fill("#8a8a8a", a))
    c.drawRect(skia.Rect.MakeXYWH(x, y + ph - 130, pw, 130), fill("#f7f3ee"))
    c.drawRRect(skia.RRect.MakeRectXY(skia.Rect.MakeXYWH(x + 30, y + ph - 105, pw - 160, 76), 38, 38), fill("#ffffff"))
    c.drawString("Message", x + 70, y + ph - 55, font("Poppins-Regular", 28), fill("#9a9a9a"))
    c.restore()


def flower(c, x, y, s, bloom, petal, center="#ffd45a", n=6, t=0.0, kind="round"):
    """A single flower; bloom 0 (bud) .. 1 (open)."""
    sway = math.sin(t * 1.2 + x * 0.01) * 4
    stem = skia.Path()
    stem.moveTo(x, y + 260 * s)
    stem.quadTo(x + sway * 2, y + 120 * s, x + sway, y)
    c.drawPath(stem, stroke("#4f8a5a", 9 * s))
    for side in (-1, 1):
        lf = path_from([(x + sway * 0.5, y + 150 * s), (x + side * 60 * s, y + 120 * s), (x + side * 90 * s, y + 140 * s),
                        (x + side * 50 * s, y + 165 * s)])
        c.drawPath(lf, fill("#5f9a5f"))
    cx, cy = x + sway, y
    b = smoothstep(bloom)
    if b < 0.05:
        c.drawPath(ellipse(cx, cy, 16 * s, 28 * s), fill(shade(petal, -0.1)))
        c.drawPath(ellipse(cx, cy + 10 * s, 18 * s, 14 * s), fill("#4f8a5a"))
        return
    if b > 0.6:
        c.drawCircle(cx, cy, 120 * s * b, fill(petal, shader=radial((cx, cy), 120 * s * b, [(petal, 0.35 * b), (petal, 0)])))
    for k in range(n):
        a = 2 * math.pi * k / n + t * 0.05
        L = (30 + 50 * b) * s
        wdt = (10 + 22 * b) * s
        c.save()
        c.translate(cx, cy)
        c.rotate(math.degrees(a))
        pp = path_from([(0, 0), (wdt, -L * 0.45), (0, -L), (-wdt, -L * 0.45)], tension=0.7)
        c.drawPath(pp, fill(petal, shader=linear((0, 0), (0, -L), [shade(petal, -0.15), shade(petal, 0.25)])))
        c.restore()
    c.drawCircle(cx, cy, (8 + 10 * b) * s, fill(center))


def flowers_metaphor(c, t, dur, W=1080, H=1920):
    """Different flowers, different seasons: some already open, one late bloomer opens slowly, glowing."""
    early = [(150, 1180, 0.9, "#ff8a5c"), (330, 1260, 0.75, "#ff6f61"), (900, 1210, 0.85, "#f7a8c4"),
             (760, 1320, 0.7, "#ffb35c"), (60, 1380, 0.65, "#f26b8a"), (1010, 1390, 0.6, "#ff9a7a")]
    for (x, y, s, col_) in early:
        flower(c, x, y, s, 1.0, col_, t=t)
    # the late bloomer – night jasmine (raat ki rani) – white, opens through the shot
    k = clamp((t - 0.6) / max(dur - 1.4, 1.0))
    flower(c, 540, 1030, 1.35, ease_in_out(k), "#fbf7ee", center="#f3e4a6", n=5, t=t)
    # rising sparkles around it as it opens
    r = random.Random(4)
    for i in range(30):
        ph = (t * 0.4 + r.random()) % 1
        a = r.random() * math.tau
        rad = 60 + ph * 260
        c.drawCircle(540 + math.cos(a) * rad, 1030 + math.sin(a) * rad * 0.6 - ph * 200, 3 + 3 * (1 - ph),
                     fill("#fff3c4", 0.8 * (1 - ph) * k))


def divine_particles(c, cx, cy, t, strength, radius=420, n=70, seed=11):
    """Golden motes converging on a point (appearance) – strength 0..1."""
    if strength <= 0:
        return
    r = random.Random(seed)
    for i in range(n):
        a = r.random() * math.tau + t * 0.6
        ph = (r.random() + t * 0.5) % 1
        rad = radius * (1 - ph)
        x = cx + math.cos(a) * rad
        y = cy + math.sin(a) * rad * 1.3
        c.drawCircle(x, y, 2 + 4 * ph, fill(r.choice(["#fff1c4", "#ffd98a", "#cdd8ff"]), strength * (0.3 + 0.7 * ph), blur=1.5))
    c.drawCircle(cx, cy, radius * 0.9, fill("#fff1c4", shader=radial((cx, cy), radius * 0.9,
                                                                     [("#fff6dd", 0.5 * strength), ("#fff6dd", 0)])))
