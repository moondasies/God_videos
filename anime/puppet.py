"""Bring painted cut-outs to life: organic warp motion + blink + audio-driven mouth.

This is *not* a vector puppet: the pixels are the sheet's painted artwork. Motion comes from a
smooth displacement field (cv2.remap), so there are no rigid 2D pivots:
  * head sway / tilt / nod around the neck, fading smoothly into the shoulders
  * breathing (subtle chest rise)
  * hair sway (only hair pixels, more at the tips)
  * blinks painted with the character's own skin tone + lash line
  * mouth opening shaped like an anime mouth, driven by the voice energy (frame-accurate)
"""
from __future__ import annotations

import math

import cv2
import numpy as np


def smoothstep(x):
    x = np.clip(x, 0, 1)
    return x * x * (3 - 2 * x)


class PaintedActor:
    def __init__(self, rgba: np.ndarray, meta: dict, kind="girl", seed=0.0, hair_amp=1.0):
        self.base = rgba.astype(np.float32) / 255.0
        self.h, self.w = rgba.shape[:2]
        self.meta = meta
        self.kind = kind
        self.seed = seed
        yy, xx = np.mgrid[0:self.h, 0:self.w].astype(np.float32)
        self.xx, self.yy = xx, yy
        a = self.base[..., 3]
        rgb = self.base[..., :3]
        v = rgb.max(-1)
        s = (rgb.max(-1) - rgb.min(-1)) / (v + 1e-6)
        if "pivot" in meta:
            px, py = meta["pivot"]
            self.pivot = (px, py)
            face_x = meta["mouth"][0]
            chin = meta["chin_y"]
        else:  # generic figure / head: pivot at the bottom centre
            px, py = self.w * 0.5, self.h * 0.92
            self.pivot = (px, py)
            face_x, chin = px, self.h * 0.45
        # head weight: 1 above the chin, fading to 0 by the pivot (neck/shoulders)
        self.w_head = smoothstep((py - yy) / max(1.0, (py - chin) * 1.2)).astype(np.float32)
        if "pivot" not in meta:
            self.w_head = smoothstep((py - yy) / (self.h * 0.9)).astype(np.float32)
        # hair mask: dark pixels inside the cut-out, away from the face centre, stronger lower down
        dark = ((v < (0.42 if kind == "girl" else 0.36)) & (a > 0.5)).astype(np.float32)
        if kind == "mahadev":
            dark *= (s < 0.55)  # navy hair, not the dark gold/brown beads
        dark = cv2.GaussianBlur(dark, (0, 0), 6)
        lateral = smoothstep((np.abs(xx - face_x) - self.w * 0.12) / (self.w * 0.25))
        vertical = smoothstep((yy - chin * 0.55) / (self.h * 0.6))
        self.w_hair = (dark * np.maximum(lateral, 0.35) * vertical * hair_amp).astype(np.float32)
        self.w_breath = smoothstep((yy - py) / (self.h * 0.35)).astype(np.float32)
        # colours for paint-overs
        if "skin_probe" in meta:
            sx, sy = map(int, meta["skin_probe"])
            self.skin = self.base[sy - 6:sy + 6, sx - 6:sx + 6, :3].reshape(-1, 3).mean(0)
            lx, ly = map(int, meta["lip"])
            self.lip = self.base[ly - 3:ly + 3, lx - 8:lx + 8, :3].reshape(-1, 3).mean(0)
        self.mouth_dark = np.array([0.42, 0.17, 0.16] if kind == "girl" else [0.24, 0.16, 0.30], np.float32)
        self.lash = np.array([0.10, 0.06, 0.05] if kind == "girl" else [0.07, 0.06, 0.12], np.float32)

    # ------------------------------------------------------------ paint-overs
    def _paint(self, img, mask, color):
        m = mask[..., None]
        img[..., :3] = img[..., :3] * (1 - m) + color[None, None, :] * m

    def _mouth(self, img, open_):
        if open_ < 0.04 or "mouth" not in self.meta:
            return
        mx, my, hw, tilt = self.meta["mouth"]
        open_ = float(np.clip(open_, 0, 1))
        ax = hw * (0.42 - 0.06 * open_)
        ay = max(2.0, hw * 0.24 * open_)
        cy = my + ay * 0.25
        x0, x1 = int(mx - hw * 1.3), int(mx + hw * 1.3)
        y0, y1 = int(my - hw), int(my + hw * 1.4)
        sub = img[y0:y1, x0:x1]
        mask = np.zeros(sub.shape[:2], np.float32)
        c = (mx - x0, cy - y0)
        cv2.ellipse(mask, (int(c[0] * 4), int(c[1] * 4)), (int(ax * 4), int(ay * 4)), tilt, 0, 360, 1.0, -1,
                    lineType=cv2.LINE_AA, shift=2)
        mask = cv2.GaussianBlur(mask, (0, 0), 1.1)
        # lower lip highlight under the opening
        lipm = np.zeros_like(mask)
        cv2.ellipse(lipm, (int(c[0] * 4), int((c[1] + ay * 0.95) * 4)), (int(ax * 0.75 * 4), int(max(2, hw * 0.12) * 4)),
                    tilt, 0, 180, 1.0, -1, lineType=cv2.LINE_AA, shift=2)
        lipm = cv2.GaussianBlur(lipm, (0, 0), 1.6) * 0.35
        self._paint(sub, lipm, np.clip(self.lip * 1.06, 0, 1))
        self._paint(sub, mask, self.mouth_dark)
        if open_ > 0.45:  # upper teeth
            teeth = np.zeros_like(mask)
            cv2.ellipse(teeth, (int(c[0] * 4), int((c[1] - ay * 0.55) * 4)), (int(ax * 0.78 * 4), int(ay * 0.32 * 4)),
                        tilt, 0, 360, 1.0, -1, lineType=cv2.LINE_AA, shift=2)
            teeth = cv2.GaussianBlur(teeth, (0, 0), 0.9) * mask
            self._paint(sub, teeth * 0.92, np.array([0.97, 0.95, 0.93], np.float32))
        if open_ > 0.7:  # tongue
            tg = np.zeros_like(mask)
            cv2.ellipse(tg, (int(c[0] * 4), int((c[1] + ay * 0.55) * 4)), (int(ax * 0.5 * 4), int(ay * 0.35 * 4)),
                        tilt, 0, 360, 1.0, -1, lineType=cv2.LINE_AA, shift=2)
            tg = cv2.GaussianBlur(tg, (0, 0), 1.2) * mask
            self._paint(sub, tg * 0.8, np.array([0.80, 0.40, 0.42], np.float32))

    def _blink(self, img, b):
        if b < 0.12 or "eyes" not in self.meta:
            return
        for ex, ey, hw in self.meta["eyes"]:
            eh = hw * 0.62
            x0, x1 = int(ex - hw * 1.6), int(ex + hw * 1.6)
            y0, y1 = int(ey - eh * 2.2), int(ey + eh * 2.0)
            sub = img[y0:y1, x0:x1]
            cx, cy = ex - x0, ey - y0
            lid = np.zeros(sub.shape[:2], np.float32)
            cover = min(1.0, b)
            # lid grows from the top of the eye downward
            top = cy - eh * 0.95
            bottom = top + (eh * 1.75) * cover
            cv2.ellipse(lid, (int(cx * 4), int(((top + bottom) / 2) * 4)), (int(hw * 1.1 * 4), int(max(1, (bottom - top) / 2) * 4)),
                        0, 0, 360, 1.0, -1, lineType=cv2.LINE_AA, shift=2)
            lid = cv2.GaussianBlur(lid, (0, 0), 2.0)
            self._paint(sub, lid, self.skin * 0.92)
            if cover > 0.75:  # closed: lash line
                ln = np.zeros_like(lid)
                cv2.ellipse(ln, (int(cx * 4), int((cy - eh * 0.3) * 4)), (int(hw * 0.98 * 4), int(eh * 0.5 * 4)),
                            0, 15, 165, 1.0, max(2, int(hw * 0.13)) * 1, lineType=cv2.LINE_AA, shift=2)
                ln = cv2.GaussianBlur(ln, (0, 0), 0.8)
                self._paint(sub, ln, self.lash)

    # ------------------------------------------------------------ frame
    def frame(self, t, mouth_open=0.0, blink=0.0, energy=1.0, tilt_bias=0.0, nod_bias=0.0):
        img = self.base.copy()
        self._mouth(img, mouth_open)
        self._blink(img, blink)
        s = self.seed
        # organic, non-repeating head motion (sum of incommensurate sines)
        ang = (math.sin(t * 0.83 + s) * 0.9 + math.sin(t * 1.71 + s * 2.3) * 0.35) * energy + tilt_bias
        ang += mouth_open * 0.6 * math.sin(t * 6.1 + s)  # tiny talking emphasis
        ang_r = math.radians(ang)
        bob = (math.sin(t * 1.1 + s * 1.7) * 2.0 + nod_bias) * self.h / 1600
        breath = math.sin(t * 2 * math.pi / 3.6 + s) * 0.006
        sway = (math.sin(t * 1.3 + s * 0.7) + 0.4 * math.sin(t * 2.9 + s)) * self.w * 0.0065
        px, py = self.pivot
        wh = self.w_head
        ca, sa = np.cos(ang_r * wh), np.sin(ang_r * wh)
        dx, dy = self.xx - px, self.yy - py
        map_x = px + ca * dx + sa * dy
        map_y = py - sa * dx + ca * dy - bob * wh
        map_y += (self.yy - py) * breath * self.w_breath
        map_x -= sway * self.w_hair * np.sin(self.yy * 0.004 + t * 1.9 + s)
        out = cv2.remap(img, map_x.astype(np.float32), map_y.astype(np.float32), cv2.INTER_LINEAR,
                        borderMode=cv2.BORDER_CONSTANT, borderValue=(0, 0, 0, 0))
        return out
