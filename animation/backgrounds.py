"""Procedural background library (original artwork, no external assets).

Each background is a list of layers. A layer has a parallax depth (0 = infinitely far,
1 = character plane, >1 = foreground) and is either static (rendered once and cached as
an image) or live (redrawn each frame for twinkles, rain, drifting clouds...).

World space is the 1080x1920 frame with PAD px of margin on every side so cameras can
pan / push in without revealing edges.
"""
from __future__ import annotations

import math
import random

import skia

from .draw import ellipse, fill, linear, mix, noise1, path_from, radial, shade, stroke

W, H = 1080, 1920
PAD = 260

# Character tint per background ("grade"): RGB multipliers + additive light colour.
GRADES = {
    "night":   dict(mul=(0.92, 0.91, 0.98), add=(0, 2, 10)),
    "sunset":  dict(mul=(1.0, 0.90, 0.84), add=(22, 6, 0)),
    "day":     dict(mul=(1.0, 1.0, 1.0), add=(0, 0, 0)),
    "warm":    dict(mul=(1.0, 0.94, 0.86), add=(10, 4, 0)),
    "dream":   dict(mul=(0.95, 0.93, 1.0), add=(10, 6, 20)),
    "rain":    dict(mul=(0.84, 0.88, 0.96), add=(0, 2, 10)),
}


class Layer:
    def __init__(self, depth, fn, live=False):
        self.depth, self.fn, self.live = depth, fn, live


def _rng(seed):
    return random.Random(seed)


# ------------------------------------------------------------------ primitives
def sky(c, top, mid, bottom, y0=-PAD, y1=H + PAD, mid_pos=0.5):
    c.drawRect(skia.Rect.MakeLTRB(-PAD, y0, W + PAD, y1),
               fill(top, shader=linear((0, y0), (0, y1), [top, mid, bottom], [0, mid_pos, 1])))


def stars(c, n, seed, y_max, t=0.0, live=False):
    r = _rng(seed)
    for i in range(n):
        x, y = r.uniform(-PAD, W + PAD), r.uniform(-PAD, y_max)
        s = r.uniform(0.8, 2.6)
        a = r.uniform(0.35, 0.95)
        if live:
            a *= 0.6 + 0.4 * math.sin(t * r.uniform(1, 3) + i)
        c.drawCircle(x, y, s, fill("#ffffff", a))


def bokeh(c, n, seed, region, colors, rmin=6, rmax=26, alpha=0.5, t=0.0):
    r = _rng(seed)
    x0, y0, x1, y1 = region
    for i in range(n):
        x, y = r.uniform(x0, x1), r.uniform(y0, y1)
        rad = r.uniform(rmin, rmax)
        col_ = r.choice(colors)
        a = alpha * (0.6 + 0.4 * math.sin(t * r.uniform(0.5, 1.5) + i)) if t else alpha * r.uniform(0.5, 1)
        c.drawCircle(x, y, rad, fill(col_, a, blur=rad * 0.35))


def buildings(c, seed, base_y, hmin, hmax, color, win_color, win_prob=0.35, wmin=60, wmax=150,
              tanks=False, x0=-PAD, x1=W + PAD):
    r = _rng(seed)
    x = x0
    while x < x1:
        bw = r.uniform(wmin, wmax)
        bh = r.uniform(hmin, hmax)
        c.drawRect(skia.Rect.MakeLTRB(x, base_y - bh, x + bw + 1, base_y + 400), fill(color))
        if tanks and r.random() < 0.45:
            tx = x + r.uniform(10, bw - 40)
            c.drawRRect(skia.RRect.MakeRectXY(skia.Rect.MakeXYWH(tx, base_y - bh - 34, 34, 34), 6, 6), fill(shade(color, -0.2)))
            c.drawRect(skia.Rect.MakeXYWH(tx + 4, base_y - bh - 6, 4, 8), fill(shade(color, -0.2)))
            c.drawRect(skia.Rect.MakeXYWH(tx + 26, base_y - bh - 6, 4, 8), fill(shade(color, -0.2)))
        if win_color:
            for wy in range(int(base_y - bh + 14), int(base_y - 10), 26):
                for wx in range(int(x + 10), int(x + bw - 14), 22):
                    if r.random() < win_prob:
                        c.drawRect(skia.Rect.MakeXYWH(wx, wy, 10, 13), fill(win_color, r.uniform(0.5, 1)))
        x += bw + r.uniform(-6, 10)


def mountains(c, seed, base_y, peak_h, color, n=5, snow=None, jag=0.25):
    r = _rng(seed)
    pts = [(-PAD, base_y + 600), (-PAD, base_y)]
    x = -PAD
    step = (W + 2 * PAD) / n
    for i in range(n + 1):
        px = -PAD + i * step + r.uniform(-step * 0.2, step * 0.2)
        pts.append((px - step * 0.45, base_y - peak_h * r.uniform(0.2, 0.45)))
        pts.append((px, base_y - peak_h * r.uniform(0.6, 1.0)))
    pts += [(W + PAD, base_y), (W + PAD, base_y + 600)]
    p = path_from(pts, smooth=False)
    c.drawPath(p, fill(color))


def cloud(c, x, y, s, color, alpha=0.8, blur=10):
    for dx, dy, r_ in ((-60, 8, 46), (-10, -14, 60), (50, 0, 48), (95, 14, 34), (-105, 18, 30)):
        c.drawCircle(x + dx * s, y + dy * s, r_ * s, fill(color, alpha, blur=blur))


def vignette(c, strength=0.55):
    c.drawRect(skia.Rect.MakeLTRB(-PAD, -PAD, W + PAD, H + PAD),
               fill("#000000", shader=radial((W / 2, H * 0.45), H * 0.75,
                                             [("#000000", 0.0), ("#000000", 0.0), ("#000000", strength)],
                                             [0, 0.55, 1])))


# ===================================================================== backgrounds
def bedroom_night():
    def wall(c, t):
        c.drawRect(skia.Rect.MakeLTRB(-PAD, -PAD, W + PAD, H + PAD),
                   fill("#1d2340", shader=linear((0, -PAD), (0, H), ["#1a1f3b", "#262d52", "#1b1f38"])))
        # window (left)
        wx, wy, ww, wh = 40, 330, 520, 640
        c.drawRRect(skia.RRect.MakeRectXY(skia.Rect.MakeXYWH(wx - 22, wy - 22, ww + 44, wh + 44), 14, 14), fill("#3a3352"))
        c.save()
        c.clipRect(skia.Rect.MakeXYWH(wx, wy, ww, wh))
        sky(c, "#0a0f2b", "#1d2556", "#3b3f74", wy, wy + wh)
        stars(c, 60, 3, wy + wh * 0.6)
        c.drawCircle(wx + 380, wy + 140, 46, fill("#fff7dd"))
        c.drawCircle(wx + 380, wy + 140, 110, fill("#fff7dd", shader=radial((wx + 380, wy + 140), 110, [("#fff7dd", 0.35), ("#fff7dd", 0)])))
        buildings(c, 7, wy + wh, 80, 260, "#141836", "#ffd27a", 0.3, 40, 90)
        bokeh(c, 26, 11, (wx, wy + wh - 200, wx + ww, wy + wh), ["#ffcf73", "#ff9f6b", "#a8c8ff"], 4, 12, 0.6)
        c.restore()
        c.drawLine(wx + ww / 2, wy, wx + ww / 2, wy + wh, stroke("#3a3352", 16))
        c.drawLine(wx, wy + wh * 0.45, wx + ww, wy + wh * 0.45, stroke("#3a3352", 14))
        # sheer curtains
        for side, x in ((-1, wx - 40), (1, wx + ww - 60)):
            cp = path_from([(x, wy - 80), (x + 100, wy - 80), (x + 80 + side * 20, wy + wh + 60), (x - 10, wy + wh + 80)])
            c.drawPath(cp, fill("#c9b8e8", 0.18))
            for k in range(5):
                c.drawLine(x + 12 + k * 18, wy - 70, x + 4 + k * 18 + side * 6, wy + wh + 60, stroke("#e8dcff", 3, alpha=0.08))
        # shelf + books + plant (right wall)
        c.drawRect(skia.Rect.MakeXYWH(700, 600, 340, 16), fill("#5b4636"))
        r = _rng(5)
        x = 715
        for i in range(7):
            bw = r.uniform(18, 30)
            bh = r.uniform(70, 110)
            c.drawRect(skia.Rect.MakeXYWH(x, 600 - bh, bw, bh), fill(r.choice(["#7d5a8c", "#c07a5a", "#4f7d8c", "#d3b26a", "#8c4f5a"])))
            x += bw + 3
        pot = path_from([(960, 600), (1010, 600), (1000, 540), (970, 540)], smooth=False)
        c.drawPath(pot, fill("#c98c6a"))
        for a in range(-60, 70, 20):
            lf = skia.Path()
            lf.moveTo(985, 540)
            lf.quadTo(985 + a * 0.8, 480, 985 + a * 1.3, 450 + abs(a) * 0.6)
            c.drawPath(lf, stroke("#4f8a62", 9))
        # framed print
        c.drawRect(skia.Rect.MakeXYWH(760, 330, 200, 150), fill("#e9dcc6"))
        c.drawRect(skia.Rect.MakeXYWH(774, 344, 172, 122), fill("#f7c59f", shader=linear((0, 344), (0, 466), ["#f7c59f", "#e98f7a"])))
        c.drawCircle(860, 420, 30, fill("#fff1d6"))
        # fairy light wire
        wire = skia.Path()
        wire.moveTo(-PAD, 250)
        for i in range(8):
            wire.quadTo(-PAD + (i + 0.5) * 210, 330, -PAD + (i + 1) * 210, 250)
        c.drawPath(wire, stroke("#2a2a2a", 3))

    def fairy(c, t):
        for i in range(8):
            for k in range(1, 6):
                u = k / 6
                x = -PAD + (i + u) * 210
                y = 250 + 4 * 80 * u * (1 - u)
                tw = 0.55 + 0.45 * math.sin(t * 2.2 + i * 1.7 + k)
                c.drawCircle(x, y + 10, 26, fill("#ffcf73", 0.22 * tw, blur=12))
                c.drawCircle(x, y + 10, 7, fill("#ffe7b0", 0.9))

    def bed(c, t):
        # headboard
        c.drawRRect(skia.RRect.MakeRectXY(skia.Rect.MakeXYWH(-PAD, 1000, W + 2 * PAD, 520), 40, 40),
                    fill("#5a3d2e", shader=linear((0, 1000), (0, 1500), ["#6b4a37", "#3d281e"])))
        for k in range(6):
            c.drawLine(-PAD, 1050 + k * 70, W + PAD, 1050 + k * 70, stroke("#3d281e", 3, alpha=0.4))
        # lamp (right)
        c.drawCircle(990, 1060, 260, fill("#ffb860", shader=radial((990, 1060), 260, [("#ffb860", 0.45), ("#ffb860", 0)])))
        lamp = path_from([(930, 980), (1050, 980), (1080, 1090), (900, 1090)], smooth=False)
        c.drawPath(lamp, fill("#f6d9a8"))
        c.drawRect(skia.Rect.MakeXYWH(982, 1090, 16, 120), fill("#b48a5a"))
        # pillows
        for x, w_ in ((60, 420), (560, 420)):
            c.drawRRect(skia.RRect.MakeRectXY(skia.Rect.MakeXYWH(x, 1250, w_, 220), 80, 80), fill("#d9d0ea"))
            c.drawRRect(skia.RRect.MakeRectXY(skia.Rect.MakeXYWH(x, 1250, w_, 220), 80, 80), stroke("#b6a9d0", 4))

    def blanket(c, t):
        bl = path_from([(-PAD, 1640), (300, 1600), (700, 1625), (W + PAD, 1590), (W + PAD, H + PAD), (-PAD, H + PAD)])
        c.drawPath(bl, fill("#6d5a8f", shader=linear((0, 1590), (0, H), ["#7b67a0", "#4e3f6c"])))
        for k in range(-3, 14):
            c.drawLine(k * 110, 1620, k * 110 - 60, H + PAD, stroke("#4e3f6c", 4, alpha=0.5))
        c.drawPath(bl, stroke("#a596c7", 5, alpha=0.6))

    return dict(layers=[Layer(0.35, wall), Layer(0.5, fairy, live=True), Layer(0.8, bed), Layer(1.25, blanket)],
                grade="night", ambient="night_crickets")


def rooftop_sunset():
    def skyl(c, t):
        sky(c, "#33265a", "#d0607a", "#ffcf7a", -PAD, 1250, 0.55)
        c.drawRect(skia.Rect.MakeLTRB(-PAD, 1250, W + PAD, H + PAD), fill("#ffcf7a"))
        c.drawCircle(640, 1150, 380, fill("#ffe2a0", shader=radial((640, 1150), 380, [("#fff1c4", 0.9), ("#ffb36b", 0.25), ("#ffb36b", 0)], [0, 0.4, 1])))
        c.drawCircle(640, 1150, 92, fill("#fff3d0"))

    def clouds(c, t):
        for i, (x, y, s) in enumerate(((150, 420, 1.3), (760, 300, 1.0), (520, 700, 1.6), (980, 820, 1.1), (60, 950, 1.0))):
            cloud(c, x + t * (6 + i * 2), y, s, "#ffb7a0" if y > 600 else "#e3a2c0", 0.55, 14)

    def city_far(c, t):
        buildings(c, 21, 1330, 120, 320, "#7a4a6e", "#ffd88a", 0.08, 50, 120, tanks=True)
        # temple shikhara silhouette
        tp = path_from([(820, 1100), (860, 960), (880, 900), (900, 960), (940, 1100)], smooth=False)
        c.drawPath(tp, fill("#7a4a6e"))
        c.drawLine(880, 900, 880, 860, stroke("#7a4a6e", 4))
        c.drawPath(path_from([(880, 860), (905, 870), (880, 880)], smooth=False), fill("#ff9a5a"))

    def city_near(c, t):
        buildings(c, 33, 1420, 140, 380, "#4a2c4c", "#ffcf73", 0.12, 90, 200, tanks=True)

    def birds(c, t):
        for i in range(5):
            x = (t * 40 + i * 140) % (W + 400) - 200
            y = 520 + i * 26 + math.sin(t * 1.5 + i) * 10
            flap = math.sin(t * 8 + i) * 8
            b = skia.Path()
            b.moveTo(x - 14, y - flap)
            b.quadTo(x - 6, y - 4, x, y)
            b.quadTo(x + 6, y - 4, x + 14, y - flap)
            c.drawPath(b, stroke("#3d2440", 3))

    def roof(c, t):
        # rooftop floor + parapet
        c.drawRect(skia.Rect.MakeLTRB(-PAD, 1420, W + PAD, H + PAD), fill("#b9806c", shader=linear((0, 1420), (0, H), ["#c48d72", "#8a5a54"])))
        c.drawRect(skia.Rect.MakeLTRB(-PAD, 1380, W + PAD, 1440), fill("#e0ab86"))
        c.drawRect(skia.Rect.MakeLTRB(-PAD, 1440, W + PAD, 1460), fill("#8a5a54", 0.6))
        # string lights along the parapet
        wire = skia.Path()
        wire.moveTo(-PAD, 1360)
        for i in range(6):
            wire.quadTo(-PAD + (i + 0.5) * 290, 1400, -PAD + (i + 1) * 290, 1360)
        c.drawPath(wire, stroke("#3a2a2a", 2.5))
        # tulsi pot (left)
        pot = path_from([(-40, 1380), (110, 1380), (95, 1270), (-25, 1270)], smooth=False)
        c.drawPath(pot, fill("#c0603e"))
        c.drawRect(skia.Rect.MakeXYWH(-35, 1262, 140, 18), fill("#d9774f"))
        r = _rng(9)
        for i in range(22):
            a = r.uniform(-1.1, 1.1)
            L = r.uniform(80, 170)
            lf = skia.Path()
            lf.moveTo(35, 1265)
            lf.quadTo(35 + a * L * 0.3, 1265 - L * 0.6, 35 + a * L * 0.7, 1265 - L)
            c.drawPath(lf, stroke("#4c7a43", 5))
            c.drawCircle(35 + a * L * 0.7, 1265 - L, 9, fill("#5f9a52"))

    def lights(c, t):
        for i in range(6):
            for k in range(1, 6):
                u = k / 6
                x = -PAD + (i + u) * 290
                y = 1360 + 4 * 40 * u * (1 - u)
                tw = 0.6 + 0.4 * math.sin(t * 2 + i + k * 1.3)
                c.drawCircle(x, y + 8, 18, fill("#ffd98a", 0.25 * tw, blur=8))
                c.drawCircle(x, y + 8, 5.5, fill("#fff0c2"))

    return dict(layers=[Layer(0.1, skyl), Layer(0.18, clouds, live=True), Layer(0.35, city_far),
                        Layer(0.5, birds, live=True), Layer(0.6, city_near), Layer(0.95, roof),
                        Layer(0.95, lights, live=True)],
                grade="sunset", ambient="rooftop_wind")


def dream_garden():
    def skyl(c, t):
        sky(c, "#2b2458", "#8a6bb8", "#f5b9c8", -PAD, 1400, 0.6)
        c.drawRect(skia.Rect.MakeLTRB(-PAD, 1400, W + PAD, H + PAD), fill("#f5b9c8"))
        stars(c, 70, 41, 700)
        c.drawCircle(780, 420, 70, fill("#fff6dd"))
        c.drawCircle(780, 420, 200, fill("#fff6dd", shader=radial((780, 420), 200, [("#fff6dd", 0.35), ("#fff6dd", 0)])))

    def hills(c, t):
        for i, (y, col_) in enumerate(((1250, "#6b5a9c"), (1380, "#4f4a86"), (1520, "#3b3a6e"))):
            p = skia.Path()
            p.moveTo(-PAD, H + PAD)
            p.lineTo(-PAD, y)
            for k in range(7):
                x = -PAD + k * 260
                p.quadTo(x + 130, y - 80 + (k % 2) * 60, x + 260, y + (k % 3) * 20)
            p.lineTo(W + PAD, H + PAD)
            p.close()
            c.drawPath(p, fill(col_))

    def motes(c, t):
        r = _rng(77)
        for i in range(40):
            x = r.uniform(-100, W + 100) + math.sin(t * 0.6 + i) * 30
            y = (r.uniform(0, H) - t * r.uniform(15, 40)) % H
            c.drawCircle(x, y, r.uniform(2, 5), fill("#fff3c4", 0.6, blur=2))

    return dict(layers=[Layer(0.15, skyl), Layer(0.5, hills), Layer(0.9, motes, live=True)],
                grade="dream", ambient="dream_pad")


def corporate_office():
    def base(c, t):
        c.drawRect(skia.Rect.MakeLTRB(-PAD, -PAD, W + PAD, H + PAD), fill("#dfe6ea", shader=linear((0, 0), (0, H), ["#e8eef0", "#c9d3d8"])))
        # big window with blinds
        c.drawRect(skia.Rect.MakeXYWH(60, 200, 960, 900), fill("#a8d0ea", shader=linear((0, 200), (0, 1100), ["#cfe7f7", "#8fbedd"])))
        buildings(c, 51, 1100, 250, 700, "#9db7c9", "#e6f2fa", 0.25, 70, 160, x0=60, x1=1020)
        for k in range(30):
            c.drawRect(skia.Rect.MakeXYWH(60, 200 + k * 30, 960, 12), fill("#f4f6f7", 0.85))
        c.drawRect(skia.Rect.MakeXYWH(60, 200, 960, 900), stroke("#7b8a93", 14))
        # desk + monitor + plant
        c.drawRect(skia.Rect.MakeLTRB(-PAD, 1380, W + PAD, H + PAD), fill("#8c6f57"))
        c.drawRect(skia.Rect.MakeLTRB(-PAD, 1380, W + PAD, 1400), fill("#a88a70"))
        c.drawRRect(skia.RRect.MakeRectXY(skia.Rect.MakeXYWH(700, 1080, 300, 200), 10, 10), fill("#22262b"))
        c.drawRect(skia.Rect.MakeXYWH(712, 1092, 276, 176), fill("#6ea0d8", shader=linear((0, 1092), (0, 1268), ["#9cc4ee", "#4f80bd"])))
        c.drawRect(skia.Rect.MakeXYWH(835, 1280, 30, 100), fill("#22262b"))
        c.drawPath(path_from([(80, 1380), (170, 1380), (160, 1290), (90, 1290)], smooth=False), fill("#e9e3da"))
        for a in range(-50, 60, 15):
            lf = skia.Path()
            lf.moveTo(125, 1290)
            lf.quadTo(125 + a, 1200, 125 + a * 1.6, 1150 + abs(a))
            c.drawPath(lf, stroke("#5c9b6a", 10))
    return dict(layers=[Layer(0.6, base)], grade="day", ambient="office_hum")


def coffee_shop():
    def base(c, t):
        c.drawRect(skia.Rect.MakeLTRB(-PAD, -PAD, W + PAD, H + PAD), fill("#6b4a37", shader=linear((0, 0), (0, H), ["#7c5640", "#4a3125"])))
        for k in range(-3, 14):  # brick hint
            for j in range(30):
                c.drawRect(skia.Rect.MakeXYWH(k * 100 + (j % 2) * 50, j * 44, 96, 40), stroke("#5a3c2c", 2, alpha=0.5))
        c.drawRRect(skia.RRect.MakeRectXY(skia.Rect.MakeXYWH(120, 300, 420, 300), 12, 12), fill("#2b2b2b"))
        f = skia.Font(skia.Typeface.MakeDefault(), 34)
        for i, tx in enumerate(["CHAI      60", "COFFEE    90", "MAGGI     80", "SAMOSA    40"]):
            c.drawString(tx, 160, 370 + i * 56, f, fill("#f2efe6", 0.85))
        c.drawRect(skia.Rect.MakeLTRB(-PAD, 1360, W + PAD, H + PAD), fill("#3a271d"))
        c.drawRect(skia.Rect.MakeLTRB(-PAD, 1360, W + PAD, 1395), fill("#8a6248"))
        for x in (680, 880):
            c.drawRRect(skia.RRect.MakeRectXY(skia.Rect.MakeXYWH(x, 1280, 70, 80), 8, 8), fill("#f2ece2"))
            c.drawCircle(x + 70, 1315, 18, stroke("#f2ece2", 7))

    def bulbs(c, t):
        for i, x in enumerate((200, 480, 760, 1000)):
            c.drawLine(x, -PAD, x, 160, stroke("#1e1e1e", 3))
            tw = 0.85 + 0.15 * math.sin(t * 1.3 + i)
            c.drawCircle(x, 190, 140, fill("#ffbf66", shader=radial((x, 190), 140, [("#ffbf66", 0.5 * tw), ("#ffbf66", 0)])))
            c.drawCircle(x, 185, 24, fill("#ffe6b3"))
    return dict(layers=[Layer(0.6, base), Layer(0.7, bulbs, live=True)], grade="warm", ambient="cafe_murmur")


def rainy_window():
    def base(c, t):
        c.drawRect(skia.Rect.MakeLTRB(-PAD, -PAD, W + PAD, H + PAD), fill("#2b3445"))
        c.drawRect(skia.Rect.MakeXYWH(80, 200, 920, 1250), fill("#4a5d78", shader=linear((0, 200), (0, 1450), ["#6d84a3", "#33445e"])))
        buildings(c, 61, 1450, 200, 600, "#2e3b52", "#f2d48c", 0.18, 80, 180, x0=80, x1=1000)
        bokeh(c, 30, 62, (80, 900, 1000, 1450), ["#f2d48c", "#ff9e7a", "#a6c8ff"], 10, 30, 0.35)
        c.drawRect(skia.Rect.MakeXYWH(80, 200, 920, 1250), stroke("#1f2633", 26))
        c.drawLine(540, 200, 540, 1450, stroke("#1f2633", 18))
        c.drawRect(skia.Rect.MakeLTRB(-PAD, 1450, W + PAD, H + PAD), fill("#3a3238"))

    def rain(c, t):
        r = _rng(5)
        for i in range(140):
            x = r.uniform(80, 1000)
            sp = r.uniform(300, 700)
            y = (r.uniform(200, 1450) + t * sp) % 1250 + 200
            c.drawLine(x, y, x - 3, y + 26, stroke("#cfe0ff", 1.6, alpha=0.35))
        for i in range(40):  # droplets sliding on glass
            x = r.uniform(90, 990)
            y = (r.uniform(200, 1400) + t * r.uniform(20, 60)) % 1240 + 200
            c.drawCircle(x, y, r.uniform(3, 7), fill("#dfeaff", 0.35))
    return dict(layers=[Layer(0.6, base), Layer(0.8, rain, live=True)], grade="rain", ambient="rain")


def quiet_garden():
    def base(c, t):
        sky(c, "#9fd0f0", "#cfe8f5", "#eaf5e3", -PAD, 1100)
        c.drawRect(skia.Rect.MakeLTRB(-PAD, 1100, W + PAD, H + PAD), fill("#86b874", shader=linear((0, 1100), (0, H), ["#9cc983", "#5f9455"])))
        for x, s in ((80, 1.4), (950, 1.2), (500, 0.8)):
            c.drawRect(skia.Rect.MakeXYWH(x - 18 * s, 1100 - 260 * s, 36 * s, 300 * s), fill("#6e4f3a"))
            for dx, dy, rr in ((-80, -300, 120), (60, -330, 130), (0, -420, 140), (-20, -250, 110)):
                c.drawCircle(x + dx * s, 1100 + dy * s, rr * s, fill("#4f8f4f", 0.95))
                c.drawCircle(x + dx * s - 30 * s, 1100 + dy * s - 30 * s, rr * 0.5 * s, fill("#6fb06a", 0.6))
        c.drawRRect(skia.RRect.MakeRectXY(skia.Rect.MakeXYWH(300, 1320, 480, 40), 10, 10), fill("#8c6a4f"))
        for x in (330, 740):
            c.drawRect(skia.Rect.MakeXYWH(x, 1360, 20, 90), fill("#6e5240"))
        r = _rng(4)
        for i in range(60):
            c.drawCircle(r.uniform(-PAD, W + PAD), r.uniform(1450, H), r.uniform(5, 10), fill(r.choice(["#f7c6d0", "#fff1a8", "#ffffff"])))

    def leaves(c, t):
        r = _rng(8)
        for i in range(10):
            x = (r.uniform(0, W) + t * 30) % (W + 200) - 100
            y = (r.uniform(0, H) + t * 50) % H
            c.drawPath(ellipse(x, y, 8, 4), fill("#8fbf6a", 0.8))
    return dict(layers=[Layer(0.6, base), Layer(1.1, leaves, live=True)], grade="day", ambient="birds")


def night_sky():
    def base(c, t):
        sky(c, "#050818", "#141a44", "#2a2a5c", -PAD, 1500)
        # milky way band
        for i in range(30):
            c.drawCircle(100 + i * 35, 200 + i * 28, 90, fill("#a7a9ff", 0.05, blur=40))
        mountains(c, 12, 1500, 420, "#0d1028", n=4)
        c.drawRect(skia.Rect.MakeLTRB(-PAD, 1500, W + PAD, H + PAD), fill("#0d1028"))

    def tw(c, t):
        stars(c, 260, 99, 1400, t, live=True)
        y = (t * 120) % 3000
        if y < 600:  # occasional shooting star
            c.drawLine(900 - y, 200 + y * 0.4, 960 - y, 176 + y * 0.4, stroke("#ffffff", 3, alpha=0.8))
    return dict(layers=[Layer(0.3, base), Layer(0.35, tw, live=True)], grade="night", ambient="night_crickets")


def kailash():
    def base(c, t):
        sky(c, "#4f7fc4", "#9cc3ea", "#e8f1fb", -PAD, 1300)
        # sacred peak – snow-capped pyramid
        peak = path_from([(80, 1300), (540, 520), (1000, 1300)], smooth=False)
        c.drawPath(peak, fill("#6c7d99", shader=linear((300, 600), (800, 1300), ["#8a9bb6", "#4e5d78"])))
        snow = path_from([(540, 520), (400, 760), (460, 740), (520, 800), (580, 740), (650, 790), (690, 770)], smooth=False)
        c.drawPath(snow, fill("#f6f9ff"))
        for k in range(8):
            c.drawLine(540, 560 + k * 30, 540 + (k % 2 * 2 - 1) * 20, 700 + k * 50, stroke("#ffffff", 4, alpha=0.5))
        mountains(c, 3, 1300, 300, "#5a6b88", n=5)
        mountains(c, 4, 1450, 260, "#3d4b66", n=4)
        c.drawRect(skia.Rect.MakeLTRB(-PAD, 1450, W + PAD, H + PAD), fill("#3d4b66"))

    def clouds(c, t):
        for i, (x, y, s) in enumerate(((100, 1000, 1.8), (800, 1100, 2.0), (400, 1250, 2.4))):
            cloud(c, x + t * 8 * (1 + i * 0.3), y, s, "#ffffff", 0.75, 18)
    return dict(layers=[Layer(0.25, base), Layer(0.5, clouds, live=True)], grade="day", ambient="mountain_wind")


def spiritual_space():
    def base(c, t):
        c.drawRect(skia.Rect.MakeLTRB(-PAD, -PAD, W + PAD, H + PAD), fill("#2a1a3a", shader=linear((0, 0), (0, H), ["#3b2552", "#1a1026"])))
        c.drawCircle(540, 760, 520, fill("#ffcf7a", shader=radial((540, 760), 520, [("#ffcf7a", 0.35), ("#ff9a5a", 0.12), ("#ff9a5a", 0)], [0, 0.4, 1])))
        # mandala rings
        for r_, n in ((260, 24), (340, 36), (420, 48)):
            for k in range(n):
                a = 2 * math.pi * k / n
                c.drawCircle(540 + math.cos(a) * r_, 760 + math.sin(a) * r_, 8, stroke("#ffd98a", 2, alpha=0.35))
        c.drawRect(skia.Rect.MakeLTRB(-PAD, 1450, W + PAD, H + PAD), fill("#20132c"))
        # lotus
        for k in range(-3, 4):
            pt = path_from([(540, 1450), (540 + k * 45 - 28, 1380 - abs(k) * -10), (540 + k * 55, 1300 + abs(k) * 25), (540 + k * 45 + 28, 1380)])
            c.drawPath(pt, fill("#f2a7c3", 0.9))

    def diyas(c, t):
        for i, x in enumerate((140, 300, 780, 940)):
            fl = 1 + 0.15 * math.sin(t * 9 + i * 2) + 0.1 * math.sin(t * 13 + i)
            c.drawCircle(x, 1420, 80, fill("#ffb347", shader=radial((x, 1420), 80, [("#ffb347", 0.45), ("#ffb347", 0)])))
            c.drawPath(path_from([(x - 40, 1440), (x + 40, 1440), (x + 20, 1470), (x - 20, 1470)]), fill("#b5652d"))
            c.drawPath(ellipse(x, 1418 - 6 * fl, 9, 20 * fl), fill("#ffd45a"))
            c.drawPath(ellipse(x, 1422 - 4 * fl, 4, 10 * fl), fill("#fff6d0"))
    return dict(layers=[Layer(0.4, base), Layer(0.9, diyas, live=True)], grade="warm", ambient="dream_pad")


def city_street():
    def base(c, t):
        sky(c, "#2d3b6b", "#7a6aa0", "#f2a07a", -PAD, 1100)
        buildings(c, 71, 1250, 300, 800, "#3a3f5c", "#ffd88a", 0.3, 120, 260)
        c.drawRect(skia.Rect.MakeLTRB(-PAD, 1250, W + PAD, H + PAD), fill("#43425a"))
        c.drawRect(skia.Rect.MakeLTRB(-PAD, 1250, W + PAD, 1300), fill("#6b6a80"))
        for k in range(-2, 8):
            c.drawRect(skia.Rect.MakeXYWH(k * 200, 1560, 110, 16), fill("#e8e4d8", 0.8))
        for x in (120, 960):
            c.drawRect(skia.Rect.MakeXYWH(x, 700, 14, 560), fill("#2a2a35"))
            c.drawLine(x + 7, 700, x + 90 * (1 if x < 500 else -1), 700, stroke("#2a2a35", 10))
            gx = x + 90 * (1 if x < 500 else -1)
            c.drawCircle(gx, 720, 160, fill("#ffd28a", shader=radial((gx, 720), 160, [("#ffd28a", 0.45), ("#ffd28a", 0)])))

    def traffic(c, t):
        for i in range(4):
            x = (t * 260 + i * 420) % (W + 600) - 300
            c.drawCircle(x, 1480, 40, fill("#ff4a4a", 0.35, blur=14))
            c.drawCircle(W - x, 1420, 40, fill("#fff1c4", 0.35, blur=14))
    return dict(layers=[Layer(0.5, base), Layer(0.8, traffic, live=True)], grade="sunset", ambient="city")


def moral_card():
    def base(c, t):
        sky(c, "#1e1838", "#3a2a5e", "#6a3f6e", -PAD, H + PAD)
        c.drawCircle(540, 820, 600, fill("#ffcf7a", shader=radial((540, 820), 600, [("#ffcf7a", 0.25), ("#ffcf7a", 0)])))

    def mandala(c, t):
        c.save()
        c.translate(540, 820)
        c.rotate(t * 4)
        for r_, n in ((300, 36), (380, 48), (460, 60)):
            for k in range(n):
                a = 2 * math.pi * k / n
                c.drawCircle(math.cos(a) * r_, math.sin(a) * r_, 6, fill("#ffd98a", 0.25))
        for k in range(16):
            a = 2 * math.pi * k / 16
            pt = path_from([(0, 0), (math.cos(a - 0.12) * 200, math.sin(a - 0.12) * 200), (math.cos(a) * 260, math.sin(a) * 260),
                            (math.cos(a + 0.12) * 200, math.sin(a + 0.12) * 200)])
            c.drawPath(pt, stroke("#ffd98a", 2, alpha=0.18))
        c.restore()
        r = _rng(3)
        for i in range(50):
            x = r.uniform(0, W) + math.sin(t + i) * 20
            y = (r.uniform(0, H) - t * r.uniform(20, 50)) % H
            c.drawCircle(x, y, r.uniform(2, 4), fill("#fff3c4", 0.5))
    return dict(layers=[Layer(0.3, base), Layer(0.5, mandala, live=True)], grade="dream", ambient="dream_pad")


BACKGROUNDS = {
    "bedroom_night": bedroom_night,
    "rooftop_sunset": rooftop_sunset,
    "dream_garden": dream_garden,
    "corporate_office": corporate_office,
    "coffee_shop": coffee_shop,
    "rainy_window": rainy_window,
    "quiet_garden": quiet_garden,
    "night_sky": night_sky,
    "kailash": kailash,
    "spiritual_space": spiritual_space,
    "city_street": city_street,
    "moral_card": moral_card,
}

_CACHE: dict = {}


def get_background(name):
    if name not in _CACHE:
        _CACHE[name] = BACKGROUNDS[name]()
    return _CACHE[name]


def layer_image(bg_name, idx, layer, ss):
    """Render a static layer once (supersampled by ss) and cache it."""
    key = (bg_name, idx, round(ss, 2))
    if key not in _CACHE:
        w, h = int((W + 2 * PAD) * ss), int((H + 2 * PAD) * ss)
        surf = skia.Surface(w, h)
        c = surf.getCanvas()
        c.clear(skia.ColorTRANSPARENT)
        c.scale(ss, ss)
        c.translate(PAD, PAD)
        layer.fn(c, 0.0)
        _CACHE[key] = surf.makeImageSnapshot()
    return _CACHE[key]
