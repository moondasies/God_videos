"""Frame renderer: resolved episode timeline -> RGBA frames.

The renderer is deterministic: any frame can be rendered at any time, which lets the
pipeline render shots independently (parallel, cached) and build cross-dissolves by
re-rendering the end of the previous shot.
"""
from __future__ import annotations

import hashlib
import math
import random

import numpy as np
import skia

from . import props as P
from .backgrounds import GRADES, H, PAD, W, get_background, layer_image
from .characters import CHARACTERS
from .draw import (clamp, draw_text_centered, ease_in_out, fill, font, lerp, noise1,
                   smoothstep, stroke, text_width, wrap)
from .rig import (GESTURES, Pose, blend_gesture, blend_params, expr_params,
                  viseme_params)

RENDERER_VERSION = "1.0.0"

# ------------------------------------------------------------------ framing presets
FRAMINGS = {
    "two_shot": dict(actors={"girl": dict(x=318, y=1105, s=0.9, yaw=0.42),
                             "mahadev": dict(x=790, y=1095, s=0.92, yaw=-0.42)},
                     camera=dict(x=540, y=960, zoom=1.0)),
    "two_shot_wide": dict(actors={"girl": dict(x=340, y=1150, s=0.78, yaw=0.4),
                                  "mahadev": dict(x=760, y=1140, s=0.8, yaw=-0.4)},
                          camera=dict(x=540, y=960, zoom=1.0)),
    "closeup_girl": dict(actors={"girl": dict(x=540, y=1290, s=1.75, yaw=0.18)},
                         camera=dict(x=540, y=960, zoom=1.0)),
    "closeup_mahadev": dict(actors={"mahadev": dict(x=540, y=1190, s=1.5, yaw=-0.15)},
                            camera=dict(x=540, y=960, zoom=1.0)),
    "medium_girl": dict(actors={"girl": dict(x=540, y=1230, s=1.25, yaw=0.1)},
                        camera=dict(x=540, y=960, zoom=1.0)),
    "medium_mahadev": dict(actors={"mahadev": dict(x=540, y=1220, s=1.15, yaw=-0.1)},
                           camera=dict(x=540, y=960, zoom=1.0)),
    "back_wide": dict(actors={"girl": dict(x=400, y=1430, s=0.62, view="back"),
                              "mahadev": dict(x=690, y=1420, s=0.66, view="back")},
                      camera=dict(x=540, y=960, zoom=1.0)),
    "empty": dict(actors={}, camera=dict(x=540, y=960, zoom=1.0)),
}

SPEAKER_ACCENT = {"girl": "#ffb7cf", "mahadev": "#ffd36b"}
CAPTION_Y = 1440          # baseline of the main caption line (inside IG/YT safe zone)
CAPTION_MAX_W = 860


def _seed(*parts):
    return int(hashlib.md5("|".join(map(str, parts)).encode()).hexdigest()[:8], 16)


def _grade_filter(grade_name, exempt=False):
    g = GRADES.get(grade_name, GRADES["day"])
    mr, mg, mb = g["mul"]
    ar, ag, ab = g["add"]
    if exempt:  # Mahadev keeps most of his own light
        mr, mg, mb = [1 - (1 - m) * 0.35 for m in (mr, mg, mb)]
        ar, ag, ab = ar * 0.3, ag * 0.3, ab * 0.3
    m = [mr, 0, 0, 0, ar / 255,
         0, mg, 0, 0, ag / 255,
         0, 0, mb, 0, ab / 255,
         0, 0, 0, 1, 0]
    return skia.ColorFilters.Matrix(m)


# ------------------------------------------------------------------ tracks
def _event_value(events, t, blend=0.35, kind="expr"):
    """events: sorted list of (time, value). Returns blended param dict at t."""
    prev, cur = None, None
    for ev in events:
        if ev[0] <= t:
            prev, cur = cur, ev
        else:
            break
    if cur is None:
        cur = events[0]
    to_val = expr_params(cur[1]) if kind == "expr" else cur[1]
    if prev is None:
        return to_val
    k = ease_in_out((t - cur[0]) / blend)
    from_val = expr_params(prev[1]) if kind == "expr" else prev[1]
    if k >= 1:
        return to_val
    return blend_params(from_val, to_val, k) if kind == "expr" else blend_gesture(from_val, to_val, k)


def _gesture(name):
    return dict(GESTURES.get(name, GESTURES["rest"]))


class ActorTrack:
    """Precomputed per-shot animation tracks for one actor."""

    def __init__(self, name, cfg, shot):
        self.name = name
        self.cfg = cfg
        self.char = CHARACTERS[name]
        lines = shot["lines"]
        base_expr = cfg.get("expr", "neutral")
        self.expr_events = [(0.0, base_expr)]
        front_is_right = cfg.get("yaw", 0) >= 0
        base_l = cfg.get("gesture_l", cfg.get("gesture", "rest"))
        base_r = cfg.get("gesture_r", cfg.get("gesture", "rest"))
        self.gl = [(0.0, _gesture(base_l))]
        self.gr = [(0.0, _gesture(base_r))]
        self.speaking = []  # (start, end, cues, vo)
        for ln in lines:
            st, en = ln["t0"], ln["t1"]
            if ln["speaker"] == name:
                if ln.get("emotion"):
                    self.expr_events.append((st - 0.15, ln["emotion"]))
                if ln.get("emotion_end"):
                    self.expr_events.append((en - 0.4, ln["emotion_end"]))
                g = ln.get("gesture")
                if g:
                    if g.startswith("both:"):
                        gg = g.split(":", 1)[1]
                        self.gl.append((st, _gesture(gg)))
                        self.gr.append((st, _gesture(gg)))
                    else:
                        (self.gr if front_is_right else self.gl).append((st, _gesture(g)))
                        if not ln.get("gesture_hold"):
                            (self.gr if front_is_right else self.gl).append(
                                (en + 0.2, _gesture(base_r if front_is_right else base_l)))
                self.speaking.append((st, en, ln.get("cues", []), ln.get("vo", False)))
            else:
                le = ln.get("listener_emotion")
                if le:
                    self.expr_events.append((st + 0.3, le))
                lg = ln.get("listener_gesture")
                if lg:
                    (self.gr if front_is_right else self.gl).append((st + 0.3, _gesture(lg)))
        for ev in cfg.get("expr_keys", []):
            self.expr_events.append((ev[0], ev[1]))
        for ev in cfg.get("gesture_keys", []):
            arm = ev[2] if len(ev) > 2 else ("r" if front_is_right else "l")
            if arm in ("l", "both"):
                self.gl.append((ev[0], _gesture(ev[1])))
            if arm in ("r", "both"):
                self.gr.append((ev[0], _gesture(ev[1])))
        self.expr_events.sort(key=lambda e: e[0])
        self.gl.sort(key=lambda e: e[0])
        self.gr.sort(key=lambda e: e[0])
        rng = random.Random(_seed(shot["id"], name))
        self.blinks, tt = [], rng.uniform(0.6, 2.0)
        while tt < shot["duration"] + 1:
            self.blinks.append(tt)
            tt += rng.uniform(2.2, 4.6)
        for ev in self.expr_events[1:]:  # blink on expression change reads natural
            self.blinks.append(ev[0] + 0.05)
        self.blinks.sort()
        self.seed = rng.random() * 10

    def mouth_at(self, t):
        for (st, en, cues, vo) in self.speaking:
            if st <= t <= en and not vo:
                lt = t - st
                prev_shape, cur_shape, cur_start = "X", "X", 0.0
                for cu in cues:
                    if cu["start"] <= lt:
                        prev_shape, cur_shape, cur_start = cur_shape, cu["value"], cu["start"]
                    else:
                        break
                k = clamp((lt - cur_start) / 0.06)
                a, b = viseme_params(prev_shape), viseme_params(cur_shape)
                return {kk: lerp(a[kk], b[kk], k) for kk in a}, True
        return viseme_params("X"), False

    def talking(self, t):
        return any(st <= t <= en for (st, en, _, vo) in self.speaking)

    def pose(self, t, global_t):
        cfg = self.cfg
        p = Pose(t=global_t)
        p.view = cfg.get("view", "front")
        p.expr = _event_value(self.expr_events, t)
        p.arm_l = _event_value(self.gl, t, 0.5, kind="g")
        p.arm_r = _event_value(self.gr, t, 0.5, kind="g")
        p.mouth, speaking = self.mouth_at(t)
        energy = p.mouth["open"]
        base_yaw = cfg.get("yaw", 0.0)
        yaw_keys = cfg.get("yaw_keys")
        if yaw_keys:
            base_yaw = _event_scalar(yaw_keys, t, base_yaw)
        p.yaw = base_yaw + noise1(global_t * 0.5, self.seed) * 0.05 + (0.04 * math.sin(global_t * 2.3) if speaking else 0)
        base_pitch = cfg.get("pitch", 0.0)
        pk = cfg.get("pitch_keys")
        if pk:
            base_pitch = _event_scalar(pk, t, base_pitch)
        p.pitch = base_pitch + noise1(global_t * 0.4, self.seed + 3) * 0.04 + energy * 0.08
        p.roll = cfg.get("roll", 0.0) + noise1(global_t * 0.35, self.seed + 7) * 1.6 + (energy * 1.5 if speaking else 0)
        # listening nod shortly after the other speaker finishes a line
        p.breath = math.sin(global_t * 2 * math.pi / 3.8 + self.seed)
        p.sway = noise1(global_t * 0.6, self.seed + 11) * 0.4
        b = 0.0
        for bt in self.blinks:
            if bt - 0.02 <= t <= bt + 0.16:
                b = 1 - abs((t - bt - 0.07) / 0.09)
                b = clamp(b * 1.4)
        p.blink = b
        look = cfg.get("look", (0.0, 0.0))
        lk = cfg.get("look_keys")
        if lk:
            look = (_event_scalar([(e[0], e[1][0]) for e in lk], t, look[0]),
                    _event_scalar([(e[0], e[1][1]) for e in lk], t, look[1]))
        p.look = (look[0] + noise1(global_t * 0.7, self.seed + 5) * 0.08, look[1])
        p.phone_glow = cfg.get("phone_glow", 0.0)
        return p


def _event_scalar(keys, t, default):
    """keys: [(time, value)] -> eased interpolation."""
    keys = sorted(keys)
    if t <= keys[0][0]:
        return keys[0][1]
    for (t0, v0), (t1, v1) in zip(keys, keys[1:]):
        if t0 <= t <= t1:
            return lerp(v0, v1, ease_in_out((t - t0) / max(t1 - t0, 1e-3)))
    return keys[-1][1]


# ------------------------------------------------------------------ shot renderer
class ShotRenderer:
    def __init__(self, shot, episode, out_w=1080, out_h=1920):
        self.shot = shot
        self.ep = episode
        self.out_w, self.out_h = out_w, out_h
        self.k = out_w / W
        self.bg_name = shot.get("background", "bedroom_night")
        self.bg = get_background(self.bg_name)
        fr = FRAMINGS.get(shot.get("framing", "empty"), FRAMINGS["empty"])
        self.actors = []
        cfgs = {}
        for name, base in fr["actors"].items():
            cfg = dict(base)
            cfg.update(episode.get("characters", {}).get(name, {}))
            cfg.update(shot.get("actors", {}).get(name, {}))
            cfgs[name] = cfg
        for name, over in shot.get("actors", {}).items():
            if name not in cfgs and name in CHARACTERS:
                cfg = dict(over)
                cfg.update(episode.get("characters", {}).get(name, {}))
                cfg.update(over)
                cfgs[name] = cfg
        for name, cfg in cfgs.items():
            if cfg.get("hidden"):
                continue
            self.actors.append(ActorTrack(name, cfg, shot))
        cam = dict(fr["camera"])
        cam.update(shot.get("camera", {}).get("from", {}))
        cam_to = dict(cam)
        cam_to.update(shot.get("camera", {}).get("to", {}))
        self.cam0, self.cam1 = cam, cam_to
        self.max_zoom = max(cam["zoom"], cam_to["zoom"])
        self.surface = skia.Surface(out_w, out_h)

    # camera at local time t
    def camera(self, t):
        d = max(self.shot["duration"], 0.01)
        k = ease_in_out(t / d)
        return {kk: lerp(self.cam0[kk], self.cam1[kk], k) for kk in ("x", "y", "zoom")}

    def _apply_cam(self, c, cam, depth):
        z = 1 + (cam["zoom"] - 1) * min(depth, 1.6)
        cx = 540 + (cam["x"] - 540) * depth
        cy = 960 + (cam["y"] - 960) * depth
        c.translate(W / 2, H / 2)
        c.scale(z, z)
        c.translate(-cx, -cy)

    def draw(self, c, t, global_t):
        shot = self.shot
        cam = self.camera(t)
        ss = self.k * self.max_zoom * 1.05
        layers = self.bg["layers"]
        char_depth = 1.0
        stype = shot.get("type", "dialogue")
        # background layers behind the characters
        for idx, layer in enumerate(layers):
            if layer.depth > char_depth:
                continue
            self._draw_layer(c, idx, layer, cam, ss, global_t)
        if stype == "metaphor_flowers":
            c.save()
            self._apply_cam(c, cam, 1.0)
            P.flowers_metaphor(c, t, shot["duration"])
            c.restore()
        # characters
        c.save()
        self._apply_cam(c, cam, 1.0)
        for a in sorted(self.actors, key=lambda a: a.cfg.get("z", 0)):
            self._draw_actor(c, a, t, global_t)
        c.restore()
        for idx, layer in enumerate(layers):
            if layer.depth > char_depth:
                self._draw_layer(c, idx, layer, cam, ss, global_t)
        # inserts drawn in screen space
        if stype == "insert_phone_feed":
            c.drawRect(skia.Rect.MakeXYWH(0, 0, W, H), fill("#0a0c1c", 0.55))
            P.phone_feed(c, t, shot["duration"], shot.get("posts"))
        elif stype == "insert_phone_chat":
            c.drawRect(skia.Rect.MakeXYWH(0, 0, W, H), fill("#1a0c10", 0.45))
            P.phone_chat(c, t, shot["duration"], shot.get("chat_lines", ["..."]), shot.get("seen_time", "6:42 PM"))
        elif stype == "moral":
            self._moral(c, t)
        # vignette
        c.drawRect(skia.Rect.MakeXYWH(0, 0, W, H), fill("#000000", shader=skia.GradientShader.MakeRadial(
            skia.Point(W / 2, H * 0.45), H * 0.78, [skia.Color(0, 0, 0, 0), skia.Color(0, 0, 0, 0), skia.Color(0, 0, 0, 120)],
            [0, 0.6, 1])))

    def _draw_layer(self, c, idx, layer, cam, ss, global_t):
        c.save()
        self._apply_cam(c, cam, layer.depth)
        if layer.live:
            layer.fn(c, global_t)
        else:
            img = layer_image(self.bg_name, idx, layer, ss)
            c.drawImageRect(img, skia.Rect.MakeLTRB(-PAD, -PAD, W + PAD, H + PAD),
                            skia.SamplingOptions(skia.FilterMode.kLinear))
        c.restore()

    def _draw_actor(self, c, a: ActorTrack, t, global_t):
        cfg = a.cfg
        pose = a.pose(t, global_t)
        alpha = 1.0
        appear = cfg.get("appear")
        if appear:
            at, dur = appear.get("at", 0.0), appear.get("dur", 1.4)
            alpha = smoothstep((t - at) / dur)
            if t < at + dur + 0.6:
                strength = clamp(1 - abs((t - at - dur * 0.6) / (dur * 0.9)))
                hx = cfg["x"]
                hy = cfg["y"] - 240 * cfg["s"]
                P.divine_particles(c, hx, hy, global_t, strength, radius=420 * cfg["s"])
            if alpha <= 0.001:
                return
        exit_ = cfg.get("exit")
        if exit_:
            alpha *= 1 - smoothstep((t - exit_["at"]) / exit_.get("dur", 1.0))
            if alpha <= 0.001:
                return
        c.save()
        c.translate(cfg["x"], cfg["y"])
        sc = cfg["s"] * (0.97 + 0.03 * alpha)
        c.scale(sc, sc)
        p = skia.Paint()
        p.setColorFilter(_grade_filter(self.bg["grade"], exempt=(a.name == "mahadev")))
        p.setAlphaf(alpha)
        c.saveLayer(None, p)
        props = dict(cfg.get("props", {}))
        a.char.draw(c, pose, outfit=cfg.get("outfit", "blazer_plaid"), props=props)
        c.restore()
        c.restore()

    def _moral(self, c, t):
        m = self.ep.get("moral", {})
        a = smoothstep((t - 0.2) / 0.8)
        f_title = font("Kalam-Bold", 72)
        lines = wrap(m.get("roman", ""), f_title, 880)
        y = 760 - len(lines) * 45
        for i, ln in enumerate(lines):
            ai = smoothstep((t - 0.2 - i * 0.25) / 0.7)
            draw_text_centered(c, ln, 540, y + i * 96 + (1 - ai) * 30, f_title, "#fff4d6", ai, outline="#3a2454", outline_w=6)
        if m.get("english"):
            f_en = font("Poppins-Regular", 38)
            ae = smoothstep((t - 1.0) / 0.8)
            for i, ln in enumerate(wrap(m["english"], f_en, 860)):
                draw_text_centered(c, ln, 540, y + len(lines) * 96 + 50 + i * 52, f_en, "#e8dcff", ae, shadow=True)
        f_logo = font("YatraOne-Regular", 54)
        al = smoothstep((t - 1.4) / 0.8)
        draw_text_centered(c, "Mahadev & Me", 540, 1360, f_logo, "#ffd36b", al, outline="#2b1b40", outline_w=5)
        c.drawLine(380, 1390, 700, 1390, stroke("#ffd36b", 2, alpha=0.6 * al))


# ------------------------------------------------------------------ captions & titles
def caption_chunks(line, max_chars=22):
    words = line["roman"].split()
    chunks, cur = [], []
    for w_ in words:
        if cur and len(" ".join(cur + [w_])) > max_chars:
            chunks.append(cur)
            cur = []
        cur.append(w_)
    if cur:
        # never leave a tiny orphan chunk (unreadably short on screen)
        if chunks and len(" ".join(cur)) <= 8:
            if len(" ".join(chunks[-1] + cur)) <= max_chars + 4:
                chunks[-1] = chunks[-1] + cur
            else:  # rebalance: pull the previous chunk's last word down
                cur = [chunks[-1].pop()] + cur
                chunks.append(cur)
        else:
            chunks.append(cur)
    total = sum(len(" ".join(ch)) for ch in chunks) or 1
    t, out = line["t0"], []
    dur = line["t1"] - line["t0"]
    for ch in chunks:
        d = dur * len(" ".join(ch)) / total
        out.append((t, t + d, ch))
        t += d
    return out


def draw_captions(c, shot, t, subtitles="hinglish"):
    if shot.get("type") == "moral":
        return
    fnt = font("Poppins-Bold", 56)
    for ln in shot["lines"]:
        if not (ln["t0"] - 0.05 <= t <= ln["t1"] + 0.25):
            continue
        accent = SPEAKER_ACCENT.get(ln["speaker"], "#ffffff")
        for (c0, c1, words) in caption_chunks(ln):
            if c0 - 0.05 <= t <= (c1 + 0.25 if c1 >= ln["t1"] - 1e-3 else c1):
                text = " ".join(words)
                tw = text_width(text, fnt)
                pop = smoothstep((t - c0) / 0.12)
                x = 540 - tw / 2
                y = CAPTION_Y + (1 - pop) * 12
                # word-level highlight (proportional timing)
                total = len(text)
                acc = 0
                c.drawRRect(skia.RRect.MakeRectXY(skia.Rect.MakeXYWH(x - 28, y - 64, tw + 56, 88), 24, 24),
                            fill("#000000", 0.32 * pop))
                for w_ in words:
                    ww = text_width(w_ + " ", fnt)
                    w_start = c0 + (c1 - c0) * acc / total
                    active = t >= w_start
                    c.drawString(w_, x, y, fnt, stroke("#120a18", 9, alpha=pop))
                    c.drawString(w_, x, y, fnt, fill(accent if active else "#ffffff", pop))
                    x += ww
                    acc += len(w_) + 1
                if "english" in subtitles and ln.get("en"):
                    fe = font("Poppins-Regular", 34)
                    for i, l2 in enumerate(wrap(ln["en"], fe, CAPTION_MAX_W)):
                        draw_text_centered(c, l2, 540, CAPTION_Y + 70 + i * 44, fe, "#f3ecff", 0.9 * pop, outline="#120a18", outline_w=6)
                break


def draw_title(c, ep, global_t):
    tt = ep.get("title_roman")
    if not tt or global_t > 3.4:
        return
    a = smoothstep(global_t / 0.4) * (1 - smoothstep((global_t - 2.9) / 0.5))
    c.drawRect(skia.Rect.MakeXYWH(0, 150, W, 330), fill("#000000", shader=skia.GradientShader.MakeLinear(
        [skia.Point(0, 150), skia.Point(0, 480)], [skia.Color(10, 6, 24, 0), skia.Color(10, 6, 24, int(150 * a)),
                                                   skia.Color(10, 6, 24, 0)], [0, 0.5, 1])))
    f_series = font("Poppins-SemiBold", 30)
    draw_text_centered(c, "MAHADEV & ME  •  EP " + str(ep.get("number", "")), 540, 250, f_series, "#ffd36b", a, outline="#1a1030", outline_w=5)
    fnt = font("Kalam-Bold", 64)
    for i, ln in enumerate(wrap(tt, fnt, 900)):
        draw_text_centered(c, ln, 540, 335 + i * 76, fnt, "#ffffff", a, outline="#1a1030", outline_w=8)


# ------------------------------------------------------------------ episode-level frame
class EpisodeRenderer:
    def __init__(self, timeline, out_w=1080, out_h=1920):
        self.tl = timeline
        self.out_w, self.out_h = out_w, out_h
        self.k = out_w / W
        self.shots = timeline["shots"]
        self._renderers = {}
        self.surface = skia.Surface(out_w, out_h)

    def shot_renderer(self, i):
        if i not in self._renderers:
            self._renderers[i] = ShotRenderer(self.shots[i], self.tl, self.out_w, self.out_h)
        return self._renderers[i]

    def _draw_shot(self, c, i, t_local):
        sh = self.shots[i]
        self.shot_renderer(i).draw(c, t_local, sh["start"] + t_local)

    def render(self, shot_idx, t_local):
        """Return RGBA uint8 array for shot shot_idx at local time t_local."""
        sh = self.shots[shot_idx]
        c = self.surface.getCanvas()
        c.save()
        c.clear(skia.ColorBLACK)
        c.scale(self.k, self.k)
        tr = sh.get("transition_in", "cut")
        td = sh.get("transition_dur", 0.45)
        self._draw_shot(c, shot_idx, t_local)
        if t_local < td and shot_idx > 0 and tr in ("dissolve", "glow"):
            prev = self.shots[shot_idx - 1]
            a = 1 - smoothstep(t_local / td)
            p = skia.Paint()
            p.setAlphaf(a)
            c.saveLayer(None, p)
            self._draw_shot(c, shot_idx - 1, prev["duration"] + t_local)
            c.restore()
        if tr == "glow" and t_local < td * 1.6:
            g = math.sin(math.pi * clamp(t_local / (td * 1.6)))
            c.drawRect(skia.Rect.MakeXYWH(0, 0, W, H), fill("#fff6e0", 0.75 * g))
        if tr == "fade" and t_local < td:
            c.drawRect(skia.Rect.MakeXYWH(0, 0, W, H), fill("#000000", 1 - smoothstep(t_local / td)))
        if sh.get("fade_out") and t_local > sh["duration"] - sh["fade_out"]:
            c.drawRect(skia.Rect.MakeXYWH(0, 0, W, H), fill("#000000", smoothstep((t_local - sh["duration"] + sh["fade_out"]) / sh["fade_out"])))
        draw_captions(c, sh, t_local, self.tl.get("subtitles", "hinglish"))
        draw_title(c, self.tl, sh["start"] + t_local)
        c.restore()
        img = self.surface.makeImageSnapshot()
        return img.toarray(colorType=skia.kRGBA_8888_ColorType)
