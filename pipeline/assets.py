"""Generate reusable character + background reference sheets and transparent PNG poses.

    python -m pipeline assets

Writes assets/characters/{girl,mahadev}/*.png and assets/backgrounds/*.png. These are
renders of the same procedural rig used in the reels, so they are always in sync with it.
"""
from __future__ import annotations

import skia

from animation.backgrounds import BACKGROUNDS, H, W
from animation.characters import CHARACTERS, WARDROBE
from animation.draw import fill, font
from animation.rig import EXPRESSIONS, GESTURES, VISEMES, Pose, expr_params, viseme_params

from .episode import ROOT

OUT = ROOT / "assets"
BG = skia.Color(246, 240, 230)


def _pose(**kw):
    p = Pose(t=1.0)
    for k, v in kw.items():
        if k == "expr":
            p.expr = expr_params(v)
        elif k == "vis":
            p.mouth = viseme_params(v)
        elif k in ("arm_l", "arm_r"):
            setattr(p, k, dict(GESTURES[v]))
        else:
            setattr(p, k, v)
    return p


def _sheet(name, cells, cell_w, cell_h, cols, title, scale, anchor_y, outfit=None, transparent=False):
    rows = (len(cells) + cols - 1) // cols
    surf = skia.Surface(cols * cell_w, rows * cell_h + 80)
    c = surf.getCanvas()
    c.clear(skia.ColorTRANSPARENT if transparent else BG)
    c.drawString(title, 24, 54, font("Kalam-Bold", 40), fill("#3a2454"))
    ch = CHARACTERS[name]
    for i, (label, pose, out) in enumerate(cells):
        x = (i % cols) * cell_w + cell_w / 2
        y = 80 + (i // cols) * cell_h
        c.save()
        c.clipRect(skia.Rect.MakeXYWH(x - cell_w / 2, y, cell_w, cell_h))
        c.translate(x, y + anchor_y)
        c.scale(scale, scale)
        ch.draw(c, pose, outfit=out or outfit or "blazer_plaid", props={"aura": 0.0} if name == "mahadev" else {})
        c.restore()
        c.drawString(label, x - cell_w / 2 + 12, y + cell_h - 14, font("Poppins-SemiBold", 22), fill("#333"))
    return surf.makeImageSnapshot()


def build_all(log=print):
    for name in ("girl", "mahadev"):
        d = OUT / "characters" / name
        d.mkdir(parents=True, exist_ok=True)
        base_out = "blazer_plaid" if name == "girl" else None
        ay = 290 if name == "girl" else 400
        fa, fs = (310, 0.7) if name == "girl" else (345, 0.55)
        # turnaround: yaw sweep + back
        cells = [(f"yaw {y:+.1f}", _pose(yaw=y), None) for y in (-1.0, -0.6, -0.3, 0.0, 0.3, 0.6, 1.0)]
        cells.append(("back", _pose(view="back"), None))
        _sheet(name, cells, 360, 880, 4, f"{name} – turnaround (procedural 2.5D rig)", 0.62, ay, base_out).save(str(d / "turnaround.png"), skia.kPNG)
        # expressions (close-ups)
        cells = [(e, _pose(expr=e, yaw=0.2), None) for e in EXPRESSIONS]
        _sheet(name, cells, 300, 420, 6, f"{name} – expressions", fs, fa, base_out).save(str(d / "expressions.png"), skia.kPNG)
        # mouth shapes / visemes
        cells = [(f"{v}", _pose(vis=v), None) for v in VISEMES]
        _sheet(name, cells, 260, 420, 9, f"{name} – mouth shapes (Rhubarb A–H, X)", fs, fa, base_out).save(str(d / "mouth_shapes.png"), skia.kPNG)
        # blinks
        cells = [(f"blink {b:.2f}", _pose(blink=b), None) for b in (0.0, 0.5, 0.8, 1.0)]
        _sheet(name, cells, 300, 420, 4, f"{name} – eye blink states", fs, fa, base_out).save(str(d / "blinks.png"), skia.kPNG)
        # gestures
        cells = [(g, _pose(arm_r=g, yaw=0.15), None) for g in GESTURES]
        _sheet(name, cells, 360, 760, 6, f"{name} – hand gestures (screen-right arm)", 0.6, ay, base_out).save(str(d / "gestures.png"), skia.kPNG)
        # transparent single poses
        for label, pose in (("front_neutral", _pose()), ("threequarter_left", _pose(yaw=-0.5, expr="smile")),
                            ("threequarter_right", _pose(yaw=0.5, expr="smile")), ("back", _pose(view="back")),
                            ("listening", _pose(yaw=0.4, expr="thoughtful", pitch=0.1)),
                            ("talking", _pose(yaw=0.3, expr="calm", vis="C", arm_r="explain"))):
            img = _sheet(name, [("", pose, None)], 700, 1400, 1, "", 1.0, 450 if name == "girl" else 620, base_out, transparent=True)
            img.save(str(d / f"pose_{label}.png"), skia.kPNG)
    # wardrobe
    cells = [(k, _pose(yaw=0.15, expr="smile"), k) for k in WARDROBE]
    _sheet("girl", cells, 360, 880, 4, "girl – wardrobe catalogue (face/hair locked, clothes change)", 0.62, 290).save(
        str(OUT / "characters" / "girl" / "wardrobe.png"), skia.kPNG)
    # backgrounds gallery
    from animation.scene import EpisodeRenderer
    bgd = OUT / "backgrounds"
    bgd.mkdir(parents=True, exist_ok=True)
    tiles = []
    for bg in BACKGROUNDS:
        tl = {"shots": [{"id": "x", "type": "dialogue", "background": bg, "framing": "empty", "duration": 3, "start": 5, "lines": []}]}
        R = EpisodeRenderer(tl, 270, 480)
        arr = R.render(0, 1.5)
        im = skia.Image.fromarray(arr.copy(), colorType=skia.kRGBA_8888_ColorType)
        im.save(str(bgd / f"{bg}.png"), skia.kPNG)
        tiles.append((bg, im))
    cols = 6
    surf = skia.Surface(cols * 290, ((len(tiles) + cols - 1) // cols) * 530 + 70)
    c = surf.getCanvas()
    c.clear(BG)
    c.drawString("Background library (procedural, original)", 20, 50, font("Kalam-Bold", 36), fill("#3a2454"))
    for i, (n, im) in enumerate(tiles):
        x, y = 10 + (i % cols) * 290, 70 + (i // cols) * 530
        c.drawImage(im, x, y)
        c.drawString(n, x, y + 505, font("Poppins-SemiBold", 20), fill("#333"))
    surf.makeImageSnapshot().save(str(bgd / "_gallery.png"), skia.kPNG)
    log(f"assets written to {OUT}")
