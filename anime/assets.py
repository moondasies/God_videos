"""Extract animation-ready layers from the approved character sheet (free, offline).

crop (sheet coords) -> Real-ESRGAN x4 anime upscale -> ISNet-anime cut-out (alpha)
-> optional outfit recolour (girl) -> RGBA PNG + landmarks (scaled) in cache/anime_assets/.

The painted artwork itself is the source of truth, so faces, hair, ornaments and palette are
exactly the sheet's. Nothing is redrawn except: mouth-open shapes, blink lids (anime/puppet.py)
and the outfit colour (recolour only – the garment cut stays the sheet's blazer).

    python -m anime.assets            # builds every asset (about 3–6 min on 4 CPU cores, cached)
"""
from __future__ import annotations

import json
from pathlib import Path

import cv2
import numpy as np
from PIL import Image

ROOT = Path(__file__).resolve().parent.parent
SHEET = ROOT / "private" / "characters" / "sheet.webp"
OUT = ROOT / "cache" / "anime_assets"
SEG_MODEL = ROOT / "models" / "img" / "isnet-anime.onnx"

# box = (x0, y0, x1, y1) on the 1536x1024 sheet; landmarks in sheet coords.
# eyes: (cx, cy, half_width); mouth: (cx, cy, half_width, tilt_deg); pivot: neck point for head sway.
REGIONS = {
    "girl_portrait": dict(box=(770, 58, 1122, 478), cutout=True, outfit=True,
                          eyes=[(899, 205, 17), (956, 199, 15)], mouth=(934, 255, 27, -6.0),
                          pivot=(930, 318), chin_y=292, skin_probe=(900, 228), lip=(934, 260)),
    "mahadev_portrait": dict(box=(0, 40, 374, 484), cutout=True,
                             eyes=[(213, 199, 15), (266, 200, 14)], mouth=(240, 240, 21, 7.0),
                             pivot=(250, 330), chin_y=286, skin_probe=(225, 222), lip=(240, 244)),
    "girl_full_front": dict(box=(1086, 104, 1180, 396), cutout=True, outfit=True),
    "mahadev_full_front": dict(box=(332, 98, 424, 414), cutout=True),
    "girl_surprised": dict(box=(1182, 628, 1268, 742), cutout=True, outfit=True),
    "girl_happy_closed": dict(box=(1354, 628, 1438, 742), cutout=True, outfit=True),
    "girl_thoughtful": dict(box=(1354, 492, 1438, 604), cutout=True, outfit=True),
    "girl_peaceful": dict(box=(1438, 628, 1522, 742), cutout=True, outfit=True),
    "mahadev_calm": dict(box=(405, 492, 493, 604), cutout=True),
    "mahadev_compassionate": dict(box=(405, 628, 493, 748), cutout=True),
    "mahadev_blessing": dict(box=(662, 628, 750, 748), cutout=True),
    "detail_moon": dict(box=(171, 838, 244, 927), cutout=False),
    "detail_m_eye": dict(box=(21, 838, 100, 926), cutout=False),
    "detail_rudraksha": dict(box=(104, 838, 166, 977), cutout=False),
    "detail_snake": dict(box=(248, 838, 320, 927), cutout=False),
    "detail_trishul": dict(box=(326, 838, 377, 977), cutout=False),
    "detail_g_eye": dict(box=(804, 843, 892, 944), cutout=False),
    "detail_g_necklace": dict(box=(966, 843, 1023, 944), cutout=False),
}

# Outfit recolours (the sheet's beige plaid blazer -> new colour, shading + weave kept).
OUTFITS = {
    "rose_blazer": dict(hue=(200, 92, 120), label="dusty-rose blazer, black tee"),
    "teal_blazer": dict(hue=(40, 118, 122), label="deep-teal blazer, black tee"),
    "original": None,
}

_SEG = None


def _segment(rgb):
    """ISNet-anime matting -> float alpha (0..1)."""
    global _SEG
    import os
    os.environ.setdefault("U2NET_HOME", str(SEG_MODEL.parent))  # use the local model, no download
    from rembg import new_session, remove
    if _SEG is None:
        _SEG = new_session("isnet-anime")
    m = remove(Image.fromarray(rgb), session=_SEG, only_mask=True, post_process_mask=False)
    m = np.array(m).astype(np.float32) / 255.0
    return np.clip((m - 0.1) / 0.8, 0, 1)


def _outfit_mask(rgb, alpha, protect=None, top_y=0):
    """Jacket region: inside the character, below top_y, not dark (hair / black tee), not skin/gold."""
    hsv = cv2.cvtColor(rgb, cv2.COLOR_RGB2HSV).astype(np.float32)
    h, s, v = hsv[..., 0] * 2, hsv[..., 1] / 255, hsv[..., 2] / 255
    skin_or_gold = (s > 0.42) & (h > 8) & (h < 55)
    m = (alpha > 0.5) & (v > 0.30) & (s < 0.46) & ~skin_or_gold
    m[:int(top_y)] = False
    m = m.astype(np.uint8) * 255
    if protect is not None:
        m[protect] = 0
    m = cv2.morphologyEx(m, cv2.MORPH_CLOSE, np.ones((11, 11), np.uint8))
    m = cv2.morphologyEx(m, cv2.MORPH_OPEN, np.ones((5, 5), np.uint8))
    n, lab, stats, _ = cv2.connectedComponentsWithStats(m)
    keep = np.zeros_like(m)
    for i in range(1, n):
        if stats[i, cv2.CC_STAT_AREA] > 0.01 * m.size:
            keep[lab == i] = 255
    # fill small holes (plaid lines, buttons) inside the jacket
    inv = cv2.bitwise_not(keep)
    n2, lab2, st2, _ = cv2.connectedComponentsWithStats(inv)
    for i in range(1, n2):
        if st2[i, cv2.CC_STAT_AREA] < 0.002 * m.size:
            keep[lab2 == i] = 255
    keep = (keep.astype(np.float32) / 255) * (alpha > 0.5)
    return cv2.GaussianBlur(keep, (0, 0), 1.5)


def _main_component(alpha, keep_ratio=0.045):
    """Drop neighbouring sheet figures caught in the crop; keep the main character (+ big props)."""
    m = (alpha > 0.4).astype(np.uint8)
    n, lab, stats, _ = cv2.connectedComponentsWithStats(m)
    if n <= 2:
        return alpha
    areas = stats[1:, cv2.CC_STAT_AREA]
    big = areas.max()
    W_ = m.shape[1]
    keep = np.zeros_like(m)
    for i in range(1, n):
        x, w_, area = stats[i, cv2.CC_STAT_LEFT], stats[i, cv2.CC_STAT_WIDTH], stats[i, cv2.CC_STAT_AREA]
        edge = x <= 2 or x + w_ >= W_ - 2          # neighbouring sheet figure sliced by the crop
        if area == big or (area >= keep_ratio * big and not (edge and area < 0.35 * big)):
            keep[lab == i] = 1
    keep = cv2.dilate(keep, np.ones((5, 5), np.uint8))
    return alpha * keep


def recolour(rgb, alpha, target, protect=None, top_y=0):
    m = _outfit_mask(rgb, alpha, protect, top_y)[..., None]
    lum = cv2.cvtColor(rgb, cv2.COLOR_RGB2GRAY).astype(np.float32) / 255
    base = np.array(target, np.float32) / 255
    # luminance-preserving tint: keep weave/shading, map mid-grey of the fabric to the target colour
    shaded = np.clip(base[None, None, :] * (lum[..., None] / 0.72) ** 1.05, 0, 1)
    out = rgb.astype(np.float32) / 255 * (1 - m) + shaded * m
    return (out * 255 + 0.5).astype(np.uint8), m[..., 0]


def build(name, spec, sheet, outfit="rose_blazer", force=False):
    from .upscale import upscale4
    OUT.mkdir(parents=True, exist_ok=True)
    tag = f"{name}__{outfit if spec.get('outfit') else 'na'}"
    png, meta_p = OUT / f"{tag}.png", OUT / f"{tag}.json"
    if png.exists() and meta_p.exists() and not force:
        return png, json.loads(meta_p.read_text())
    x0, y0, x1, y1 = spec["box"]
    crop = np.array(sheet.crop((x0, y0, x1, y1)))
    up = upscale4(crop)
    S = 4
    if spec.get("cutout"):
        alpha = _main_component(_segment(up), spec.get("keep_ratio", 0.045))
    else:
        alpha = np.ones(up.shape[:2], np.float32)
    meta = {"size": [up.shape[1], up.shape[0]], "outfit": None}

    def tr(p):
        return [(p[0] - x0) * S, (p[1] - y0) * S]
    if "eyes" in spec:
        meta["eyes"] = [tr(e[:2]) + [e[2] * S] for e in spec["eyes"]]
        mx, my = tr(spec["mouth"][:2])
        meta["mouth"] = [mx, my, spec["mouth"][2] * S, spec["mouth"][3]]
        meta["pivot"] = tr(spec["pivot"])
        meta["chin_y"] = (spec["chin_y"] - y0) * S
        meta["skin_probe"] = tr(spec["skin_probe"])
        meta["lip"] = tr(spec["lip"])
    if spec.get("outfit") and OUTFITS.get(outfit):
        protect = np.zeros(up.shape[:2], bool)
        if "eyes" in spec:  # portrait: jacket starts below the chin, never touch the face/neck/necklace
            top = meta["chin_y"] + 0.03 * up.shape[0]
        else:  # small heads / full body: jacket is below the head
            top = up.shape[0] * (0.62 if "full" not in name else 0.22)
            if "full" in name:  # jacket only: keep trousers/sneakers below the hips untouched
                protect[int(up.shape[0] * 0.47):, :] = True
        up, _ = recolour(up, alpha, OUTFITS[outfit]["hue"], protect, top)
        meta["outfit"] = outfit
    rgba = np.dstack([up, (alpha * 255 + 0.5).astype(np.uint8)])
    Image.fromarray(rgba, "RGBA").save(png)
    meta_p.write_text(json.dumps(meta, indent=1))
    return png, meta


def build_all(outfit="rose_blazer", force=False, log=print):
    if not SHEET.exists():
        raise SystemExit(f"Character sheet missing: {SHEET}  (see docs/inputs.md)")
    sheet = Image.open(SHEET).convert("RGB")
    res = {}
    for name, spec in REGIONS.items():
        p, meta = build(name, spec, sheet, outfit, force)
        res[name] = (p, meta)
        log(f"  asset {name:24s} {meta['size'][0]}x{meta['size'][1]}")
    return res


def load(name, outfit="rose_blazer"):
    spec = REGIONS[name]
    tag = f"{name}__{outfit if spec.get('outfit') else 'na'}"
    png = OUT / f"{tag}.png"
    if not png.exists():
        build(name, spec, Image.open(SHEET).convert("RGB"), outfit)
    img = np.array(Image.open(png).convert("RGBA"))
    meta = json.loads((OUT / f"{tag}.json").read_text())
    return img, meta


if __name__ == "__main__":
    import sys
    build_all(sys.argv[1] if len(sys.argv) > 1 else "rose_blazer", force="--force" in sys.argv)
