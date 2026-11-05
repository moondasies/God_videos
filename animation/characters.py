"""The two permanent characters: the Girl ("Meera" working name) and Mahadev.

Both are drawn procedurally from a locked identity spec (``IDENTITY`` dicts below), so the
face, hair and accessories are identical in every frame of every episode.  Only the
outfit (girl) and props change between episodes.  See docs/character_bible.md.
"""
from __future__ import annotations

import math

import skia

from .draw import (capsule, clamp, ellipse, fill, linear, mix, noise1, path_from, radial,
                   shade, stroke)
from .rig import (FaceProj, Pose, draw_brow, draw_eye, draw_hand, draw_mouth, draw_nose,
                  face_outline, ik)

# =====================================================================================
# Locked identity specs (derived from the approved character sheet palette).
# Changing these changes the character – QA verifies their hash (pipeline/qa.py).
# =====================================================================================
GIRL_IDENTITY = {
    "skin": "#f2c6a6", "skin_shadow": "#d9a184", "blush": "#ec9a8e",
    "hair": "#2b1b15", "hair_mid": "#3c271e", "hair_hi": "#6e4c3b",
    "iris": "#5a361f", "lash": "#1d120e", "brow": "#3a251b",
    "lip": "#c96f6b", "mouth_line": "#8e4644", "mouth_in": "#5b1f24",
    "gold": "#d8a640", "sclera": "#fbf6f1",
    "face_half_w": 90, "chin": 114, "crown": -132, "jaw": 0.6,
    "eye_w": 56, "eye_h": 31, "eye_x": 40, "brow_y": -40, "mouth_y": 64, "mouth_w": 34,
    "height_cm": 163,
}

MAHADEV_IDENTITY = {
    "skin": "#8091c4", "skin_shadow": "#5f6fa3", "skin_hi": "#a6b4de",
    "hair": "#1a1b2c", "hair_mid": "#272a42", "hair_hi": "#4a4f78",
    "iris": "#6b4523", "lash": "#120f1a", "brow": "#15131f",
    "lip": "#6c5c8f", "mouth_line": "#3c3157", "mouth_in": "#3a1c2c",
    "gold": "#e0ab3c", "moon": "#f6ead0", "rudraksha": "#7b4526", "rudraksha_hi": "#a8683d",
    "tiger": "#e39a2e", "tiger_stripe": "#2a1a10", "fur": "#f3e7cf", "sash": "#c8611f",
    "snake": "#55705a", "snake_belly": "#d9cf9e", "snake_dark": "#2e4234",
    "tripundra": "#f8f5ee", "tilak": "#d0412c", "sclera": "#f7f3ec",
    "face_half_w": 96, "chin": 120, "crown": -138, "jaw": 0.66,
    "eye_w": 56, "eye_h": 26, "eye_x": 42, "brow_y": -38, "mouth_y": 70, "mouth_w": 40,
    "height_cm": 188,
}

# Wardrobe catalogue for the girl. Each entry: colours + construction flags.
WARDROBE = {
    "blazer_plaid": dict(label="Office: beige plaid blazer, black tee, black trousers",
                         base="#1f1c1f", panel="#cdb99d", plaid=("#9e8466", "#b4574a"),
                         sleeve="#cdb99d", sleeve_len="long", neck="round", panels=True),
    "home_tshirt": dict(label="Bedroom: oversized lilac T-shirt, pyjamas",
                        base="#b8a9d9", sleeve="#b8a9d9", sleeve_len="short", neck="round"),
    "kurta": dict(label="Spiritual: simple peach cotton kurta",
                  base="#f1d1a7", sleeve="#f1d1a7", sleeve_len="three_quarter", neck="kurta",
                  trim="#c9902e"),
    "hoodie": dict(label="Winter: slate hoodie", base="#6c7d98", sleeve="#6c7d98",
                   sleeve_len="long", neck="hood"),
    "casual_denim": dict(label="Coffee shop: cream top, denim jacket, jeans",
                         base="#f3ece0", panel="#6f8fb8", sleeve="#6f8fb8", sleeve_len="long",
                         neck="round", panels=True, stitch="#d9a35a"),
    "winter_jacket": dict(label="Winter street: hoodie under olive jacket",
                          base="#6c7d98", panel="#59613f", sleeve="#59613f", sleeve_len="long",
                          neck="hood", panels=True),
    "home_kurti": dict(label="Emotional / home: soft teal kurti",
                       base="#7fb3ad", sleeve="#7fb3ad", sleeve_len="short", neck="kurta",
                       trim="#f2e6c9"),
}


HS = 1.3  # global stylised head scale (see Character.HS)


def _breath_scale(pose):
    return 1 + 0.010 * pose.breath


class Character:
    identity: dict = {}
    shoulder = 170.0
    upper_arm = 175.0
    forearm = 160.0
    hand = 52.0
    arm_w = (58, 44, 38)

    HS = HS  # stylised head scale (bigger head = more expressive cartoon read)

    def head_anchor(self, pose: Pose):
        return (pose.yaw * 6, -212 + pose.pitch * 7 - pose.breath * 1.5)

    # -------------------------------------------------------------- arms
    def arm_points(self, pose: Pose, side):
        g = pose.arm_l if side < 0 else pose.arm_r
        reach = self.upper_arm + self.forearm
        S = (side * self.shoulder * (1 - 0.08 * abs(pose.yaw) * (1 if side * pose.yaw < 0 else 0)),
             42 - pose.breath * 2)
        wx, wy = g["w"]
        # gesture x is a fraction of shoulder half-width (screen-left arm), mirrored for the right
        T = ((wx if side < 0 else -wx) * self.shoulder, S[1] + wy * reach * 0.6)
        E, W = ik(S, T, self.upper_arm, self.forearm * g.get("fs", 1.0), outward=side)
        return S, E, W, g["hand"]

    def draw_arm(self, c, pose, side, sleeve, sleeve_len, skin):
        S, E, W, hand = self.arm_points(pose, side)
        w0, w1, w2 = self.arm_w
        cuff = shade(sleeve, -0.12) if sleeve else None
        up = capsule(S, E, w0, w1)
        fo = capsule(E, W, w1, w2)
        if sleeve is None:
            c.drawPath(up, fill(skin))
            c.drawPath(fo, fill(skin))
            c.drawPath(up, stroke(shade(skin, -0.3), 2, alpha=0.5))
            c.drawPath(fo, stroke(shade(skin, -0.3), 2, alpha=0.5))
        else:
            c.drawPath(fo, fill(skin))
            if sleeve_len == "long":
                c.drawPath(fo, fill(sleeve))
                c.drawPath(capsule(E, W, w1 * 1.05, w2 * 1.15), stroke(cuff, 2.5, alpha=0.6))
            elif sleeve_len == "three_quarter":
                mid = (E[0] + (W[0] - E[0]) * 0.55, E[1] + (W[1] - E[1]) * 0.55)
                c.drawPath(capsule(E, mid, w1 * 1.08, w1), fill(sleeve))
            else:
                c.drawPath(fo, stroke(shade(skin, -0.3), 2, alpha=0.5))
            if sleeve_len == "short":
                c.drawPath(up, fill(skin))
                mid = (S[0] + (E[0] - S[0]) * 0.62, S[1] + (E[1] - S[1]) * 0.62)
                sl = capsule(S, mid, w0 * 1.08, w1 * 1.12)
                c.drawPath(sl, fill(sleeve))
                c.drawPath(sl, stroke(shade(sleeve, -0.25), 2.5, alpha=0.6))
            else:
                c.drawPath(up, fill(sleeve))
                c.drawPath(up, stroke(shade(sleeve, -0.25), 2.5, alpha=0.5))
            # elbow fold
            c.drawCircle(E[0], E[1], w1 * 0.25, fill(shade(sleeve, -0.2), 0.25, blur=6))
        ang = math.atan2(W[1] - E[1], W[0] - E[0])
        draw_hand(c, W, ang, hand, skin, self.hand, side)
        return W


# =====================================================================================
class Girl(Character):
    identity = GIRL_IDENTITY
    shoulder = 156.0
    upper_arm = 150.0
    forearm = 136.0
    hand = 54.0
    arm_w = (56, 44, 34)

    def style(self):
        I = self.identity
        return dict(skin=I["skin"], sclera=I["sclera"], iris_col=I["iris"], lash=I["lash"],
                    lash_w=4.2, flick=True, tilt=2.0, iris=0.5, brow=I["brow"], brow_w=7.5,
                    lip=I["lip"], mouth_line=I["mouth_line"], mouth_line_w=3.0,
                    mouth_in=I["mouth_in"], mouth_h=30, nose_w=11)

    # ---------------------------------------------------------------- draw
    def draw(self, c: skia.Canvas, pose: Pose, outfit="blazer_plaid", props=None):
        props = props or {}
        O = WARDROBE.get(outfit, WARDROBE["blazer_plaid"])
        I = self.identity
        c.save()
        c.scale(1, _breath_scale(pose))
        H = self.head_anchor(pose)
        if pose.view == "back":
            self._draw_back(c, pose, O, H)
            c.restore()
            return
        if O.get("neck") == "hood":
            self._hood_back(c, pose, O)
        self._back_hair(c, pose, H)
        self._neck(c, pose)
        self._torso(c, pose, O)
        self._head(c, pose, H)
        self._front_hair(c, pose, H)
        phone_pos = None
        for side in (-1, 1):
            g = pose.arm_l if side < 0 else pose.arm_r
            W = self.draw_arm(c, pose, side, O["sleeve"], O["sleeve_len"], I["skin"])
            if g["hand"] == "phone":
                phone_pos = W if phone_pos is None else ((phone_pos[0] + W[0]) / 2, (phone_pos[1] + W[1]) / 2)
        if phone_pos is not None and props.get("phone", True):
            self._phone(c, phone_pos, pose)
        c.restore()

    # ---------------------------------------------------------------- parts
    def _hair_sway(self, pose, k=1.0):
        return (pose.sway * 10 + noise1(pose.t * 0.9, 3) * 3) * k

    def _back_hair(self, c, pose, H):
        I = self.identity
        hx, hy = H
        HS = self.HS
        sw = self._hair_sway(pose)
        s = math.sin(pose.yaw * 0.6)
        top = hy - 150 * HS
        pts = [(hx - 10 * HS, top), (hx + 85 * HS, top + 25), (hx + 112 * HS - s * 20, hy - 20 * HS), (hx + 122 * HS - s * 18, hy + 90 * HS),
               (138 + sw, 120), (152 + sw * 1.4, 260), (140 + sw * 1.8, 330), (80 + sw * 1.6, 345),
               (-80 + sw * 1.6, 345), (-140 + sw * 1.8, 330), (-152 + sw * 1.4, 260), (-138 + sw, 120),
               (hx - 122 * HS - s * 18, hy + 90 * HS), (hx - 112 * HS - s * 20, hy - 20 * HS), (hx - 85 * HS, top + 25)]
        p = path_from(pts, tension=0.55)
        c.drawPath(p, fill(I["hair"], shader=linear((0, top), (0, 340), [I["hair_mid"], I["hair"], shade(I["hair"], -0.2)])))
        c.save()
        c.clipPath(p, doAntiAlias=True)
        # strand lines
        for k in range(-5, 6):
            x0 = hx + k * 20
            sp = skia.Path()
            sp.moveTo(x0, hy + 40 * HS)
            sp.cubicTo(x0 * 1.1, 120, x0 * 1.25 + sw, 220, x0 * 1.3 + sw * 1.6, 330)
            c.drawPath(sp, stroke(I["hair_hi"], 2, alpha=0.18))
        c.restore()

    def _neck(self, c, pose):
        I = self.identity
        hx, hy = self.head_anchor(pose)
        p = path_from([(-30 + hx * 0.4, hy + 70 * HS), (30 + hx * 0.4, hy + 70 * HS), (34, 10), (40, 40),
                       (-40, 40), (-34, 10)], smooth=False)
        c.drawPath(p, fill(I["skin"], shader=linear((0, hy + 60 * HS), (0, 40), [shade(I["skin"], -0.2), I["skin"]])))
        c.save()
        c.clipPath(p, doAntiAlias=True)
        c.drawPath(ellipse(hx * 0.6 + math.sin(pose.yaw * 0.6) * 25, hy + 112 * HS, 60, 26),
                   fill(I["skin_shadow"], 0.7, blur=9))
        c.restore()

    def _torso_path(self, pose, widen=1.0):
        by = pose.yaw * 0.45
        f_l = 1 - 0.12 * max(by, 0)
        f_r = 1 - 0.12 * max(-by, 0)
        pts = [(-34, -6), (-118 * f_l, 18), (-168 * f_l * widen, 52), (-180 * f_l * widen, 120),
               (-160 * f_l * widen, 330), (-148 * f_l, 520), (-156 * f_l, 920), (156 * f_r, 920),
               (148 * f_r, 520), (160 * f_r * widen, 330),
               (180 * f_r * widen, 120), (168 * f_r * widen, 52), (118 * f_r, 18), (34, -6)]
        return path_from(pts, tension=0.45), by * 40

    def _torso(self, c, pose, O):
        I = self.identity
        tp, off = self._torso_path(pose)
        base = O["base"]
        c.drawPath(tp, fill(base, shader=linear((-180, 0), (180, 0),
                                                [shade(base, 0.08), base, shade(base, -0.15)])))
        c.save()
        c.clipPath(tp, doAntiAlias=True)
        # folds
        for fx, fy in ((-90, 220), (70, 260), (-30, 420)):
            fp = skia.Path()
            fp.moveTo(fx + off, fy)
            fp.quadTo(fx + 30 + off, fy + 60, fx + 10 + off, fy + 140)
            c.drawPath(fp, stroke(shade(base, -0.25), 10, alpha=0.18, blur=6))
        # neckline
        neck = O.get("neck", "round")
        if neck in ("round", "hood", "kurta"):
            scoop = ellipse(off * 0.6, 4, 52, 40 if neck != "kurta" else 30)
            c.drawPath(scoop, fill(I["skin"]))
            c.drawPath(ellipse(off * 0.6 - 22, 30, 26, 4), fill(I["skin_shadow"], 0.35, blur=3))
            c.drawPath(ellipse(off * 0.6 + 22, 30, 26, 4), fill(I["skin_shadow"], 0.35, blur=3))
            rib = skia.Path()
            rib.addArc(skia.Rect.MakeLTRB(off * 0.6 - 54, -38, off * 0.6 + 54, 46), 0, 180)
            c.drawPath(rib, stroke(shade(base, -0.2), 7, alpha=0.9))
            if neck == "kurta":
                slit = skia.Path()
                slit.moveTo(off * 0.6, 42)
                slit.lineTo(off * 0.6, 120)
                c.drawPath(slit, stroke(shade(base, -0.3), 3))
                for k in range(9):
                    a = math.radians(10 + k * 20)
                    c.drawCircle(off * 0.6 + math.cos(a) * 60, 4 + math.sin(a) * 47, 3.2, fill(O.get("trim", "#c9902e")))
        # necklace (identity accessory – always worn)
        ch = skia.Path()
        ch.moveTo(off * 0.6 - 38, 2)
        ch.quadTo(off * 0.6, 120, off * 0.6 + 38, 2)
        c.drawPath(ch, stroke(I["gold"], 1.6, alpha=0.95))
        c.drawPath(ellipse(off * 0.6, 66, 5, 7), fill(I["gold"]))
        c.drawCircle(off * 0.6 - 1.5, 64, 1.6, fill("#fff6d0"))
        if neck == "hood":
            for sx in (-24, 24):
                c.drawLine(off * 0.6 + sx, 40, off * 0.6 + sx * 1.1, 190, stroke("#e8e4dc", 4))
                c.drawRect(skia.Rect.MakeXYWH(off * 0.6 + sx * 1.1 - 3, 186, 6, 16), fill("#c0b9ad"))
        if O.get("panels"):
            self._panels(c, pose, O, off)
        c.restore()
        c.drawPath(tp, stroke(shade(base, -0.4), 2.2, alpha=0.35))

    def _panels(self, c, pose, O, off):
        """Open jacket / blazer panels with lapels."""
        pc = O["panel"]
        for side in (-1, 1):
            pts = [(side * 40 + off * 0.6, -4), (side * 125, 16), (side * 172, 52), (side * 184, 130),
                   (side * 176, 920), (side * 62 + off, 920), (side * 58 + off, 340), (side * 66 + off * 0.8, 160)]
            panel = path_from(pts, smooth=False)
            c.drawPath(panel, fill(pc, shader=linear((side * 60, 0), (side * 190, 0), [shade(pc, 0.06), shade(pc, -0.12)])))
            if "plaid" in O:
                c.save()
                c.clipPath(panel, doAntiAlias=True)
                a, b = O["plaid"]
                for k in range(-10, 30):
                    c.drawLine(k * 26, -20, k * 26 + 30, 720, stroke(a, 2.0, alpha=0.45))
                    c.drawLine(-200, k * 26, 200, k * 26 + 6, stroke(a, 2.0, alpha=0.45))
                for k in range(-4, 12):
                    c.drawLine(k * 78 + 10, -20, k * 78 + 40, 720, stroke(b, 2.2, alpha=0.35))
                    c.drawLine(-200, k * 78 + 15, 200, k * 78 + 21, stroke(b, 2.2, alpha=0.35))
                c.restore()
            if "stitch" in O:
                st = skia.Path()
                st.moveTo(side * 64 + off * 0.8, 170)
                st.lineTo(side * 62 + off, 690)
                p = stroke(O["stitch"], 2, alpha=0.8)
                p.setPathEffect(skia.DashPathEffect.Make([8, 6], 0))
                c.drawPath(st, p)
            # lapel
            lap = path_from([(side * 40 + off * 0.6, -4), (side * 92, 40), (side * 112, 92),
                             (side * 90, 118), (side * 112, 150), (side * 66 + off * 0.8, 300)], smooth=False)
            c.drawPath(lap, fill(shade(pc, -0.06)))
            c.drawPath(lap, stroke(shade(pc, -0.35), 2.2, alpha=0.7))
            c.drawPath(panel, stroke(shade(pc, -0.4), 2.2, alpha=0.6))
        c.drawCircle(-62 + off, 420, 9, fill("#5a3b26"))
        c.drawCircle(-62 + off, 420, 9, stroke("#2f1f15", 1.5))

    def _hood_back(self, c, pose, O):
        hood = path_from([(-150, 40), (-120, -10), (-60, -40), (60, -40), (120, -10), (150, 40), (0, 70)])
        c.drawPath(hood, fill(shade(O["base"], -0.12)))

    def _head(self, c, pose, H):
        I = self.identity
        st = self.style()
        c.save()
        c.translate(*H)
        c.rotate(pose.roll)
        c.scale(self.HS, self.HS)
        P = FaceProj(pose.yaw, pose.pitch)
        outline = face_outline(P, I["face_half_w"], I["chin"], I["crown"], I["jaw"])
        s = math.sin(P.phi)
        # ear + earring on the visible far side
        ear_side = -1 if s >= 0 else 1
        c.drawPath(outline, fill(I["skin"], shader=radial((-20 + s * 30, -30), 150,
                                                          [shade(I["skin"], 0.08), I["skin"], shade(I["skin"], -0.12)],
                                                          [0, 0.6, 1])))
        c.save()
        c.clipPath(outline, doAntiAlias=True)
        # turned-away side shadow
        c.drawPath(ellipse(-s * 120, 20, 70, 160), fill(I["skin_shadow"], 0.35 * abs(s) * 2 + 0.08, blur=30))
        if pose.phone_glow > 0:
            c.drawPath(ellipse(s * 20, 80, 120, 110), fill("#bcd6ff", 0.28 * pose.phone_glow, blur=40))
        c.restore()
        # blush
        for side in (-1, 1):
            bx = P.x(side * 55)
            c.drawPath(ellipse(bx, P.y(38), 22 * P.sx(side * 55), 12),
                       fill(I["blush"], 0.22 + 0.2 * max(pose.expr["smile"], 0), blur=9))
        # eyes / brows
        for side in (-1, 1):
            ex = P.x(side * I["eye_x"])
            draw_eye(c, ex, P.y(0), I["eye_w"], I["eye_h"], P.sx(side * I["eye_x"]), pose, st, side, P)
            draw_brow(c, P.x(side * (I["eye_x"] + 2)), P.y(I["brow_y"]), 50, side, pose, st, P.sx(side * 40))
        draw_nose(c, P.x(0, 1.18), P.y(36, 1.1), st, P)
        draw_mouth(c, P.x(0, 1.06), P.y(I["mouth_y"], 1.05), I["mouth_w"], pose, st, P.sx(0))
        # top hair: cap with centre parting
        self._hair_cap(c, P)
        # earring peeking under the hair on the far side
        ex = ear_side * (I["face_half_w"] - 2) + s * 14
        c.drawCircle(ex, P.y(48), 8.5, stroke(I["gold"], 3.2))
        c.drawCircle(ex - 2, P.y(42), 2, fill("#fff3c4", 0.9))
        c.restore()

    def _hair_cap(self, c, P):
        I = self.identity
        s = math.sin(P.phi)
        part = s * 62
        hw = I["face_half_w"]
        crown = I["crown"]
        pts = [(part, crown - 6), (part + 50 + s * 10, crown + 4), (hw + 8, -78), (hw + 16 - s * 10, 10),
               (hw + 22 - s * 8, 120), (hw - 6 - s * 14, 100), (hw - 14 - s * 8, 10), (hw * 0.84 + s * 18, -52),
               (part + 30, -84), (part + 2, -96),
               (part - 30, -84), (-hw * 0.84 + s * 18, -52), (-hw + 14 - s * 8, 10), (-hw + 6 - s * 14, 100),
               (-hw - 22 - s * 8, 120), (-hw - 16 - s * 10, 10), (-hw - 8, -78), (part - 50 + s * 10, crown + 4)]
        cap = path_from(pts, tension=0.5)
        c.drawPath(cap, fill(I["hair"], shader=linear((0, crown), (0, 120), [I["hair_mid"], I["hair"]])))
        c.save()
        c.clipPath(cap, doAntiAlias=True)
        # sheen
        for side in (-1, 1):
            sh = skia.Path()
            sh.moveTo(part + side * 12, crown + 8)
            sh.quadTo(part + side * 60, crown + 12, part + side * (hw - 4), -70)
            c.drawPath(sh, stroke(I["hair_hi"], 9, alpha=0.45, blur=4))
            for k in (0.3, 0.6):
                ln = skia.Path()
                ln.moveTo(part + side * 6, crown + 4)
                ln.quadTo(part + side * hw * k * 1.2, crown + 20 + 30 * k, part + side * (hw * 0.6 + 20 * k), -96 + k * 40)
                c.drawPath(ln, stroke(shade(I["hair"], -0.3), 1.8, alpha=0.6))
        c.restore()
        c.drawLine(part, crown - 4, part + 1, -96, stroke(shade(I["skin"], -0.25), 2.2, alpha=0.7))

    def _front_hair(self, c, pose, H):
        I = self.identity
        hx, hy = H
        HS = self.HS
        s = math.sin(pose.yaw * 0.6)
        sw = self._hair_sway(pose, 1.2)
        rr = math.radians(pose.roll)
        for side in (-1, 1):
            far = (side * s) < 0
            if far and abs(s) > 0.35:
                continue  # far-side lock hidden behind the shoulder line
            x0 = hx + (side * (I["face_half_w"] + 4) + s * 10) * HS
            top = hy - 40 * HS
            pts = [(x0 - side * 18, top - 30), (x0 + side * 30, top), (x0 + side * 40, hy + 80 * HS),
                   (side * 150 + sw, 70), (side * 150 + sw * 1.4, 220), (side * 128 + sw * 1.7, 300),
                   (side * 110 + sw * 1.6, 270), (side * 104 + sw * 1.2, 150), (x0 - side * 6 + sw * 0.4, hy + 120 * HS),
                   (x0 - side * 16, hy + 20 * HS)]
            pts = [(px + (py - hy) * rr * 0.6 * 0, py) for px, py in pts]
            lock = path_from(pts, tension=0.5)
            c.drawPath(lock, fill(I["hair"], shader=linear((0, hy - 60 * HS), (0, 300), [I["hair_mid"], I["hair"]])))
            for k in range(4):
                ln = skia.Path()
                ln.moveTo(x0 + side * (2 + k * 8), top)
                ln.cubicTo(x0 + side * (16 + k * 8), hy + 80 * HS, side * (118 + k * 8) + sw, 120,
                           side * (114 + k * 7) + sw * 1.6, 270)
                c.drawPath(ln, stroke(I["hair_hi"] if k % 2 else shade(I["hair"], -0.3), 2.2, alpha=0.4))

    def _draw_back(self, c, pose, O, H):
        I = self.identity
        hx, hy = H
        HS = self.HS
        tp, _ = self._torso_path(pose)
        c.drawPath(tp, fill(O.get("panel", O["base"])))
        for side in (-1, 1):
            self.draw_arm(c, pose, side, O["sleeve"], O["sleeve_len"], I["skin"])
        sw = self._hair_sway(pose)
        pts = [(hx, hy - 150 * HS), (hx + 95 * HS, hy - 120 * HS), (hx + 116 * HS, hy), (hx + 120 * HS, hy + 90 * HS), (150 + sw, 150),
               (148 + sw * 1.5, 320), (90 + sw * 1.7, 350), (-90 + sw * 1.7, 350), (-148 + sw * 1.5, 320),
               (-150 + sw, 150), (hx - 120 * HS, hy + 90 * HS), (hx - 116 * HS, hy), (hx - 95 * HS, hy - 120 * HS)]
        hp = path_from(pts, tension=0.5)
        c.drawPath(hp, fill(I["hair"], shader=linear((0, hy - 150 * HS), (0, 350), [I["hair_mid"], I["hair"]])))
        for k in range(-6, 7):
            ln = skia.Path()
            ln.moveTo(hx + k * 6, hy - 140 * HS)
            ln.cubicTo(hx + k * 18, hy, k * 22 + sw, 200, k * 23 + sw * 1.6, 340)
            c.drawPath(ln, stroke(I["hair_hi"], 2.2, alpha=0.3))
        c.drawPath(ellipse(hx - 30 * HS, hy - 100 * HS, 40, 18), fill(I["hair_hi"], 0.35, blur=8))

    def _phone(self, c, pos, pose):
        x, y = pos
        c.save()
        c.translate(x, y - 40)
        c.rotate(-8 + pose.yaw * 10)
        r = skia.RRect.MakeRectXY(skia.Rect.MakeLTRB(-38, -70, 38, 70), 10, 10)
        c.drawRRect(r, fill("#16171c"))
        inner = skia.RRect.MakeRectXY(skia.Rect.MakeLTRB(-33, -64, 33, 64), 7, 7)
        c.drawRRect(inner, fill("#9fc3ff", shader=linear((0, -64), (0, 64), ["#cfe2ff", "#7aa7f0"])))
        for k in range(4):
            c.drawRect(skia.Rect.MakeXYWH(-26, -52 + k * 30, 52, 18), fill("#ffffff", 0.6))
        c.restore()
        # thumbs over the phone
        I = self.identity
        for side in (-1, 1):
            c.drawPath(capsule((x + side * 34, y - 10), (x + side * 18, y - 40), 18, 15), fill(I["skin"]))
            c.drawPath(capsule((x + side * 34, y - 10), (x + side * 18, y - 40), 18, 15),
                       stroke(shade(I["skin"], -0.35), 1.8, alpha=0.7))


# =====================================================================================
class Mahadev(Character):
    identity = MAHADEV_IDENTITY
    shoulder = 196.0
    upper_arm = 170.0
    forearm = 152.0
    hand = 64.0
    arm_w = (78, 60, 46)

    def style(self):
        I = self.identity
        return dict(skin=I["skin"], sclera=I["sclera"], iris_col=I["iris"], lash=I["lash"],
                    lash_w=4.6, flick=True, tilt=3.0, iris=0.52, brow=I["brow"], brow_w=9.5,
                    lip=I["lip"], mouth_line=I["mouth_line"], mouth_line_w=3.2,
                    mouth_in=I["mouth_in"], mouth_h=30, nose_w=14, tongue="#c56d7a")

    def head_anchor(self, pose: Pose):
        return (pose.yaw * 7, -236 + pose.pitch * 7 - pose.breath * 1.5)

    def draw(self, c: skia.Canvas, pose: Pose, outfit="default", props=None):
        props = props or {}
        I = self.identity
        c.save()
        H = self.head_anchor(pose)
        self._aura(c, pose, H, props.get("aura", 1.0))
        c.scale(1, _breath_scale(pose))
        if pose.view == "back":
            self._draw_back(c, pose, H)
            c.restore()
            return
        if props.get("trishul"):
            self._trishul(c, pose, props.get("trishul_side", 1))
        self._back_hair(c, pose, H)
        self._snake_back(c, pose)
        self._neck(c, pose, H)
        self._torso(c, pose)
        self._head(c, pose, H)
        self._front_locks(c, pose, H)
        self._snake(c, pose, H)
        self._malas(c, pose)
        for side in (-1, 1):
            self._arm(c, pose, side)
        c.restore()

    # ---------------------------------------------------------------- parts
    def _aura(self, c, pose, H, k):
        if k <= 0:
            return
        hx, hy = H
        HS = self.HS
        pulse = 0.85 + 0.15 * math.sin(pose.t * 1.6)
        c.drawCircle(hx, hy - 10 * HS, 330 * pulse, fill("#ffffff", shader=radial(
            (hx, hy - 10 * HS), 330 * pulse, [("#fff3cf", 0.42 * k), ("#c9d4ff", 0.18 * k), ("#c9d4ff", 0.0)],
            [0, 0.5, 1])))

    def _arm(self, c, pose, side):
        I = self.identity
        S, E, W, hand = self.arm_points(pose, side)
        w0, w1, w2 = self.arm_w
        sk = I["skin"]
        up = capsule(S, E, w0, w1)
        fo = capsule(E, W, w1, w2)
        for p in (up, fo):
            c.drawPath(p, fill(sk, shader=linear(S, (S[0] + side * 60, S[1]), [I["skin_hi"], sk])))
            c.drawPath(p, stroke(I["skin_shadow"], 2.2, alpha=0.6))
        # rudraksha arm band + bracelet
        for (A, B, f) in ((S, E, 0.42), (E, W, 0.82)):
            bx, by = A[0] + (B[0] - A[0]) * f, A[1] + (B[1] - A[1]) * f
            ang = math.atan2(B[1] - A[1], B[0] - A[0]) + math.pi / 2
            wdt = (w0 if A is S else w1) * 0.55
            for k in range(-3, 4):
                px, py = bx + math.cos(ang) * k * wdt / 3.3, by + math.sin(ang) * k * wdt / 3.3
                c.drawCircle(px, py, 6.2, fill(I["rudraksha"]))
                c.drawCircle(px - 1.8, py - 1.8, 2, fill(I["rudraksha_hi"], 0.9))
        ang = math.atan2(W[1] - E[1], W[0] - E[0])
        draw_hand(c, W, ang, hand, sk, self.hand, side, outline=I["skin_shadow"])

    def _back_hair(self, c, pose, H):
        I = self.identity
        hx, hy = H
        HS = self.HS
        sw = noise1(pose.t * 0.7, 5) * 6 + pose.sway * 8
        top = hy - 120 * HS
        pts = [(hx, top), (hx + 110 * HS, top + 30), (hx + 138 * HS, hy + 40 * HS), (205 + sw, 60), (232 + sw * 1.3, 200),
               (212 + sw * 1.6, 330), (176 + sw * 1.5, 300), (150 + sw, 360), (-150 + sw, 360),
               (-176 + sw * 1.5, 300), (-212 + sw * 1.6, 330), (-232 + sw * 1.3, 200), (-205 + sw, 60),
               (hx - 138 * HS, hy + 40 * HS), (hx - 110 * HS, top + 30)]
        p = path_from(pts, tension=0.6)
        c.drawPath(p, fill(I["hair"], shader=linear((0, top), (0, 360), [I["hair_mid"], I["hair"]])))
        c.save()
        c.clipPath(p, doAntiAlias=True)
        for k in range(-7, 8):
            wv = skia.Path()
            x0 = hx + k * 22
            wv.moveTo(x0, hy + 10 * HS)
            for j in range(1, 7):
                yy = hy + 10 * HS + j * 55
                wv.quadTo(x0 * (1 + j * 0.05) + (14 if j % 2 else -14) + sw * j / 6, yy - 27,
                          x0 * (1 + j * 0.06) + sw * j / 6, yy)
            c.drawPath(wv, stroke(I["hair_hi"], 3, alpha=0.25))
        c.restore()

    def _neck(self, c, pose, H):
        I = self.identity
        hx, hy = H
        HS = self.HS
        p = path_from([(-44 + hx * 0.4, hy + 70 * HS), (44 + hx * 0.4, hy + 70 * HS), (54, 8), (70, 40),
                       (-70, 40), (-54, 8)], smooth=False)
        c.drawPath(p, fill(I["skin"], shader=linear((0, hy + 60 * HS), (0, 40), [I["skin_shadow"], I["skin"]])))

    def _torso(self, c, pose):
        I = self.identity
        by = pose.yaw * 0.45
        fl, fr = 1 - 0.1 * max(by, 0), 1 - 0.1 * max(-by, 0)
        pts = [(-50, -4), (-150 * fl, 20), (-214 * fl, 62), (-226 * fl, 140), (-196 * fl, 330),
               (-178 * fl, 920), (178 * fr, 920), (196 * fr, 330), (226 * fr, 140), (214 * fr, 62),
               (150 * fr, 20), (50, -4)]
        tp = path_from(pts, tension=0.45)
        sk = I["skin"]
        c.drawPath(tp, fill(sk, shader=radial((-50, 100), 330, [I["skin_hi"], sk, I["skin_shadow"]], [0, 0.55, 1])))
        off = by * 40
        c.save()
        c.clipPath(tp, doAntiAlias=True)
        # subtle anatomy: collarbones, chest, abdomen
        for side in (-1, 1):
            cb = skia.Path()
            cb.moveTo(off + side * 18, 34)
            cb.quadTo(off + side * 80, 22, off + side * 140, 40)
            c.drawPath(cb, stroke(I["skin_shadow"], 4, alpha=0.45, blur=2))
            pec = skia.Path()
            pec.moveTo(off + side * 12, 120)
            pec.quadTo(off + side * 90, 205, off + side * 170, 150)
            c.drawPath(pec, stroke(I["skin_shadow"], 7, alpha=0.4, blur=5))
            c.drawPath(ellipse(off + side * 95, 85, 70, 40), fill(I["skin_hi"], 0.25, blur=18))
        c.drawLine(off, 140, off * 1.1, 420, stroke(I["skin_shadow"], 5, alpha=0.3, blur=4))
        for k in range(3):
            for side in (-1, 1):
                c.drawPath(ellipse(off + side * 34, 270 + k * 62, 26, 22), stroke(I["skin_shadow"], 3, alpha=0.18, blur=3))
        c.restore()
        # tiger-skin drape over his left shoulder (screen right) across the chest
        drape = path_from([(70, -2), (160, 12), (226, 70), (230, 160), (196, 340), (130, 480),
                           (-60, 620), (-140, 700), (-178, 700), (-60, 560), (40, 380), (96, 210), (90, 80)],
                          tension=0.4)
        self._tiger(c, drape, (-180, 0), (230, 700))
        fur = skia.Path()
        fur.moveTo(70, -2)
        fur.cubicTo(96, 80, 96, 210, 40, 380)
        fur.cubicTo(0, 470, -60, 560, -178, 700)
        p = stroke(I["fur"], 16)
        p.setPathEffect(skia.DiscretePathEffect.Make(10, 4, 7))
        c.drawPath(fur, p)
        # waist: sash + tiger dhoti edge
        sash = path_from([(-200, 560), (200, 545), (196, 610), (-198, 625)], smooth=False)
        c.drawPath(sash, fill(I["sash"], shader=linear((0, 545), (0, 625), [shade(I["sash"], 0.15), shade(I["sash"], -0.2)])))
        knot = path_from([(60, 580), (100, 570), (110, 640), (90, 720), (70, 700), (78, 630)])
        c.drawPath(knot, fill(shade(I["sash"], -0.1)))
        dh = path_from([(-198, 620), (198, 605), (200, 940), (-200, 940)], smooth=False)
        self._tiger(c, dh, (-200, 600), (200, 940))
        c.drawPath(tp, stroke(I["skin_shadow"], 2.5, alpha=0.5))

    def _tiger(self, c, path, a, b):
        I = self.identity
        c.drawPath(path, fill(I["tiger"], shader=linear(a, b, [shade(I["tiger"], 0.12), I["tiger"], shade(I["tiger"], -0.2)])))
        c.save()
        c.clipPath(path, doAntiAlias=True)
        x0, y0 = a
        x1, y1 = b
        k = 0
        y = y0 - 40
        while y < y1 + 40:
            for x in range(int(x0) - 40, int(x1) + 40, 95):
                jx = ((k * 37 + x) % 50) - 25
                st = skia.Path()
                st.moveTo(x + jx, y)
                st.cubicTo(x + jx + 18, y + 12, x + jx + 36, y - 4, x + jx + 58, y + 14)
                c.drawPath(st, stroke(I["tiger_stripe"], 9, alpha=0.9))
                st2 = skia.Path()
                st2.moveTo(x + jx + 10, y + 22)
                st2.quadTo(x + jx + 26, y + 30, x + jx + 40, y + 26)
                c.drawPath(st2, stroke(I["tiger_stripe"], 5, alpha=0.75))
            y += 52
            k += 1
        c.restore()
        c.drawPath(path, stroke(shade(I["tiger"], -0.45), 2, alpha=0.6))

    def _malas(self, c, pose):
        I = self.identity
        off = pose.yaw * 0.45 * 40
        for depth, n in ((150, 24), (230, 30)):
            for k in range(n + 1):
                t = k / n
                ang = math.pi * t
                x = off + math.cos(ang) * (60 + depth * 0.3)
                y = 10 + math.sin(ang) * depth
                c.drawCircle(x, y, 7.5, fill(I["rudraksha"]))
                c.drawCircle(x - 2, y - 2, 2.6, fill(I["rudraksha_hi"]))
            c.drawCircle(off, 10 + depth + 10, 11, fill(I["rudraksha"]))

    def _snake_back(self, c, pose):
        I = self.identity
        back = skia.Path()
        back.moveTo(-86, 18)
        back.cubicTo(-70, -40, 70, -40, 86, 18)
        c.drawPath(back, stroke(I["snake_dark"], 30))
        c.drawPath(back, stroke(shade(I["snake"], -0.25), 24))

    def _snake(self, c, pose, H):
        """Vasuki coiled around the neck, hood raised at Mahadev's right shoulder (screen left)."""
        I = self.identity
        off = pose.yaw * 14
        sway = math.sin(pose.t * 1.1) * 5
        # front of the coil + tail hanging over his left chest (screen right)
        body = skia.Path()
        body.moveTo(-176 + sway, -40)
        body.cubicTo(-170, 20, -120, 30, -86 + off * 0.3, 18)
        body.cubicTo(-60 + off, 80, 60 + off, 80, 86 + off * 0.3, 18)
        body.cubicTo(118, 40, 132, 110, 112, 170)
        body.cubicTo(100, 205, 84, 214, 76, 236)
        c.drawPath(body, stroke(I["snake_dark"], 34))
        c.drawPath(body, stroke(I["snake"], 27))
        c.drawPath(body, stroke(shade(I["snake"], 0.25), 7, alpha=0.5))
        pe = stroke(I["snake_dark"], 5, alpha=0.55)
        pe.setPathEffect(skia.DashPathEffect.Make([5, 13], 0))
        c.drawPath(body, pe)
        # raised neck + hood beside the jaw
        neck = skia.Path()
        neck.moveTo(-176 + sway, -40)
        neck.cubicTo(-182 + sway, -80, -178 + sway, -110, -172 + sway, -140)
        c.drawPath(neck, stroke(I["snake_dark"], 34))
        c.drawPath(neck, stroke(I["snake"], 28))
        x, y = -172 + sway, -168
        hood = path_from([(x, y - 62), (x + 44, y - 36), (x + 50, y + 12), (x + 26, y + 56), (x, y + 66),
                          (x - 26, y + 56), (x - 50, y + 12), (x - 44, y - 36)], tension=0.55)
        c.drawPath(hood, fill(I["snake"], shader=radial((x, y - 10), 70, [shade(I["snake"], 0.18), I["snake"], I["snake_dark"]], [0, 0.6, 1])))
        c.drawPath(hood, stroke(I["snake_dark"], 3))
        belly = path_from([(x, y - 44), (x + 18, y - 20), (x + 16, y + 30), (x, y + 58), (x - 16, y + 30), (x - 18, y - 20)])
        c.drawPath(belly, fill(I["snake_belly"]))
        for k in range(6):
            yy = y - 30 + k * 14
            c.drawLine(x - 14, yy, x + 14, yy, stroke(shade(I["snake_belly"], -0.3), 1.6, alpha=0.8))
        # spectacle mark on hood edges
        for side in (-1, 1):
            c.drawCircle(x + side * 34, y - 12, 6, stroke(I["snake_belly"], 2.5, alpha=0.8))
        head = path_from([(x - 20, y - 56), (x - 16, y - 82), (x, y - 94), (x + 16, y - 82), (x + 20, y - 56), (x, y - 50)])
        c.drawPath(head, fill(I["snake"], shader=linear((x, y - 94), (x, y - 50), [shade(I["snake"], 0.2), I["snake"]])))
        c.drawPath(head, stroke(I["snake_dark"], 2.2))
        for side in (-1, 1):
            c.drawCircle(x + side * 9, y - 74, 3.6, fill("#f4d870"))
            c.drawCircle(x + side * 9, y - 74, 1.6, fill("#111111"))
        if (pose.t % 4.0) < 0.35:  # occasional tongue flick
            tg = skia.Path()
            tg.moveTo(x, y - 94)
            tg.lineTo(x, y - 110)
            tg.lineTo(x - 5, y - 117)
            tg.moveTo(x, y - 110)
            tg.lineTo(x + 5, y - 117)
            c.drawPath(tg, stroke("#c2394a", 2.2))

    def _head(self, c, pose, H):
        I = self.identity
        st = self.style()
        c.save()
        c.translate(*H)
        c.rotate(pose.roll)
        c.scale(self.HS, self.HS)
        P = FaceProj(pose.yaw, pose.pitch, R=104)
        s = math.sin(P.phi)
        outline = face_outline(P, I["face_half_w"], I["chin"], I["crown"], I["jaw"])
        # ears + gold hoops
        for side in (-1, 1):
            if side * s > 0.25:
                continue
            ex = side * (I["face_half_w"] - 4) + s * 18
            c.drawPath(ellipse(ex, P.y(10), 16, 30), fill(shade(I["skin"], -0.08)))
            c.drawCircle(ex + side * 2, P.y(58), 17, stroke(I["gold"], 5))
            c.drawCircle(ex + side * 2 - 6, P.y(46), 3, fill("#fff1c2"))
        c.drawPath(outline, fill(I["skin"], shader=radial((-20 + s * 30, -30), 160,
                                                          [I["skin_hi"], I["skin"], I["skin_shadow"]], [0, 0.55, 1])))
        c.save()
        c.clipPath(outline, doAntiAlias=True)
        c.drawPath(ellipse(-s * 125, 20, 70, 160), fill(I["skin_shadow"], 0.3 * abs(s) * 2 + 0.06, blur=30))
        c.restore()
        for side in (-1, 1):
            ex = P.x(side * I["eye_x"])
            draw_eye(c, ex, P.y(0), I["eye_w"], I["eye_h"], P.sx(side * I["eye_x"]), pose, st, side, P)
            draw_brow(c, P.x(side * (I["eye_x"] + 3)), P.y(I["brow_y"]), 56, side, pose, st, P.sx(side * 41))
        draw_nose(c, P.x(0, 1.2), P.y(38, 1.1), st, P)
        draw_mouth(c, P.x(0, 1.06), P.y(I["mouth_y"], 1.05), I["mouth_w"], pose, st, P.sx(0))
        # tripundra: three horizontal ash lines + red bindu
        cx = P.x(0, 1.02)
        for k in range(3):
            y = P.y(-66 + k * 10)
            ln = skia.Path()
            ln.moveTo(cx - 52 * P.sx(-40), y + 3)
            ln.quadTo(cx, y - 4, cx + 52 * P.sx(40), y + 3)
            c.drawPath(ln, stroke(I["tripundra"], 5.2, alpha=0.95))
        c.drawPath(ellipse(cx, P.y(-58), 4.2, 8), fill(I["tilak"]))
        self._hair_cap(c, P, pose)
        c.restore()

    def _hair_cap(self, c, P, pose):
        I = self.identity
        s = math.sin(P.phi)
        hw = I["face_half_w"]
        crown = I["crown"]
        cap = path_from([(s * 30, crown - 10), (hw * 0.9, crown + 14), (hw + 16, -60), (hw + 20 - s * 10, 30),
                         (hw - 4 - s * 10, 10), (hw - 8, -60), (hw * 0.55 + s * 30, -88), (s * 40, -92),
                         (-hw * 0.55 + s * 30, -88), (-hw + 8, -60), (-hw + 4 - s * 10, 10),
                         (-hw - 20 - s * 10, 30), (-hw - 16, -60), (-hw * 0.9, crown + 14)], tension=0.5)
        c.drawPath(cap, fill(I["hair"], shader=linear((0, crown), (0, 30), [I["hair_mid"], I["hair"]])))
        c.save()
        c.clipPath(cap, doAntiAlias=True)
        for side in (-1, 1):
            for k in range(3):
                ln = skia.Path()
                ln.moveTo(s * 40 + side * (10 + k * 20), -90)
                ln.quadTo(side * (40 + k * 25), crown + 10, s * 20 + side * (10 + k * 10), crown - 30)
                c.drawPath(ln, stroke(I["hair_hi"], 2.5, alpha=0.45))
        c.restore()
        # jata bun with rudraksha bands
        bx, by = s * 24, crown - 58
        bun = path_from([(bx - 62, by + 40), (bx - 58, by - 20), (bx - 30, by - 62), (bx + 30, by - 62),
                         (bx + 58, by - 20), (bx + 62, by + 40)], tension=0.6)
        c.drawPath(bun, fill(I["hair"], shader=radial((bx - 15, by - 25), 80, [I["hair_hi"], I["hair_mid"], I["hair"]])))
        top = ellipse(bx, by - 72, 34, 28)
        c.drawPath(top, fill(I["hair"], shader=radial((bx - 8, by - 82), 40, [I["hair_hi"], I["hair"]])))
        for row, (yy, rw) in enumerate(((by + 28, 60), (by - 30, 52))):
            for k in range(-6, 7):
                x = bx + k * rw / 6.5
                y = yy + (k * k) * 0.35
                c.drawCircle(x, y, 6.3, fill(I["rudraksha"]))
                c.drawCircle(x - 1.8, y - 1.8, 2.1, fill(I["rudraksha_hi"]))
        # crescent moon on his left side of the bun (screen right)
        mx, my = bx + 62, by - 40
        glow = 0.7 + 0.3 * math.sin(pose.t * 2.1)
        c.drawCircle(mx, my, 52, fill("#fff6db", shader=radial((mx, my), 52, [("#fff6db", 0.55 * glow), ("#fff6db", 0.0)])))
        moon = skia.Path()
        moon.addCircle(mx, my, 34)
        cut = skia.Path()
        cut.addCircle(mx + 15, my - 12, 30)
        cres = skia.Op(moon, cut, skia.PathOp.kDifference_PathOp)
        if cres is not None:
            c.drawPath(cres, fill(I["moon"], shader=linear((mx - 34, my), (mx + 10, my), ["#fffaf0", I["moon"]])))
            c.drawPath(cres, stroke("#d7c393", 1.8, alpha=0.8))

    def _front_locks(self, c, pose, H):
        I = self.identity
        hx, hy = H
        HS = self.HS
        s = math.sin(pose.yaw * 0.6)
        sw = noise1(pose.t * 0.8, 9) * 5 + pose.sway * 8
        for side in (-1, 1):
            if side * s < -0.35:
                continue
            x0 = hx + (side * (I["face_half_w"] + 6) + s * 12) * HS
            lock = path_from([(x0 - side * 6, hy - 60 * HS), (x0 + side * 34, hy - 20 * HS), (x0 + side * 50, hy + 60 * HS),
                              (side * 206 + sw, 40), (side * 214 + sw * 1.3, 140), (side * 196 + sw * 1.5, 230),
                              (side * 178 + sw * 1.4, 200), (side * 176 + sw, 110), (x0 + side * 8, hy + 110 * HS),
                              (x0 - side * 10, hy + 20 * HS)], tension=0.55)
            c.drawPath(lock, fill(I["hair"], shader=linear((0, hy - 60 * HS), (0, 240), [I["hair_mid"], I["hair"]])))
            for k in range(3):
                wv = skia.Path()
                wv.moveTo(x0 + side * (6 + k * 10), hy - 30 * HS)
                wv.cubicTo(x0 + side * (40 + k * 6), hy + 60 * HS, side * (176 + k * 8) + sw, 60,
                           side * (186 + k * 6) + sw * 1.4, 200)
                c.drawPath(wv, stroke(I["hair_hi"], 3, alpha=0.35))

    def _trishul(self, c, pose, side):
        I = self.identity
        x = side * 300
        c.drawLine(x, -470, x, 760, stroke("#7a5a2e", 14))
        c.drawLine(x, -470, x, 760, stroke("#a98247", 5, alpha=0.6))
        gold = I["gold"]
        prong = skia.Path()
        prong.moveTo(x - 60, -560)
        prong.quadTo(x - 64, -470, x, -455)
        prong.quadTo(x + 64, -470, x + 60, -560)
        c.drawPath(prong, stroke(gold, 12))
        c.drawLine(x, -455, x, -620, stroke(gold, 12))
        for px in (x - 60, x, x + 60):
            tip = path_from([(px - 12, -555 if px != x else -615), (px, -600 if px != x else -660),
                             (px + 12, -555 if px != x else -615)], smooth=False)
            c.drawPath(tip, fill(gold))
        # damru tied below the prongs
        dy = -420
        d = path_from([(x - 30, dy - 26), (x + 30, dy - 26), (x + 6, dy), (x + 30, dy + 26), (x - 30, dy + 26),
                       (x - 6, dy)], smooth=False)
        c.drawPath(d, fill("#a0522d"))
        c.drawPath(d, stroke("#5b2e17", 2))
        c.drawLine(x - 30, dy - 26, x + 30, dy - 26, stroke("#f2e6c9", 4))
        c.drawLine(x - 30, dy + 26, x + 30, dy + 26, stroke("#f2e6c9", 4))

    def _draw_back(self, c, pose, H):
        I = self.identity
        hx, hy = H
        HS = self.HS
        tp = path_from([(-50, -4), (-150, 20), (-214, 62), (-226, 140), (-196, 330), (-178, 920), (178, 920),
                        (196, 330), (226, 140), (214, 62), (150, 20), (50, -4)], tension=0.45)
        c.drawPath(tp, fill(I["skin"], shader=linear((0, 0), (0, 700), [I["skin"], I["skin_shadow"]])))
        for side in (-1, 1):
            self._arm(c, pose, side)
        sw = noise1(pose.t * 0.7, 5) * 6 + pose.sway * 8
        hp = path_from([(hx, hy - 140 * HS), (hx + 110 * HS, hy - 100 * HS), (hx + 130 * HS, hy + 40 * HS), (200 + sw, 80), (226 + sw * 1.3, 220),
                        (190 + sw * 1.6, 380), (-190 + sw * 1.6, 380), (-226 + sw * 1.3, 220), (-200 + sw, 80),
                        (hx - 130 * HS, hy + 40 * HS), (hx - 110 * HS, hy - 100 * HS)], tension=0.6)
        c.drawPath(hp, fill(I["hair"], shader=linear((0, hy - 140 * HS), (0, 380), [I["hair_mid"], I["hair"]])))
        for k in range(-8, 9):
            wv = skia.Path()
            x0 = hx + k * 14
            wv.moveTo(x0, hy - 100 * HS)
            for j in range(1, 8):
                yy = hy - 100 * HS + j * 70
                wv.quadTo(x0 * (1 + j * 0.15) + (14 if j % 2 else -14) + sw * j / 7, yy - 35, x0 * (1 + j * 0.17) + sw * j / 7, yy)
            c.drawPath(wv, stroke(I["hair_hi"], 3, alpha=0.3))
        # bun + moon from behind
        bun = ellipse(hx, hy - 190 * HS, 60, 52)
        c.drawPath(bun, fill(I["hair_mid"]))
        for k in range(-6, 7):
            c.drawCircle(hx + k * 9, hy - 170 * HS + k * k * 0.3, 6, fill(I["rudraksha"]))
        moon = skia.Path()
        moon.addCircle(hx - 62 * HS, hy - 225 * HS, 30)
        cut = skia.Path()
        cut.addCircle(hx - 76 * HS, hy - 236 * HS, 26)
        cres = skia.Op(moon, cut, skia.PathOp.kDifference_PathOp)
        if cres is not None:
            c.drawPath(cres, fill(I["moon"]))
        # snake tail draped over the shoulder
        tail = skia.Path()
        tail.moveTo(-60, 10)
        tail.cubicTo(-140, 20, -190, 60, -170, 130)
        c.drawPath(tail, stroke(I["snake_dark"], 26))
        c.drawPath(tail, stroke(I["snake"], 20))


GIRL = Girl()
MAHADEV = Mahadev()
CHARACTERS = {"girl": GIRL, "mahadev": MAHADEV}
