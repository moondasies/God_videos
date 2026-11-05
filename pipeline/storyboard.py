"""Storyboard sheet (rendered keyframes) + screenplay markdown for an episode."""
from __future__ import annotations

from pathlib import Path

import numpy as np
import skia

from .episode import ROOT, resolve_timeline, save_json

TW, TH = 270, 480


def script_markdown(ep, tl=None):
    L = [f"# {ep['title_roman']}  ·  _{ep.get('title_en', '')}_", "",
         f"**Series:** Mahadev & Me — Episode {ep.get('number', '')}  ",
         f"**Pillar:** {ep.get('pillar', '')}  ",
         f"**Target audience:** {ep.get('target_audience', '')}  ",
         f"**Core problem:** {ep.get('core_problem', '')}  ",
         f"**Intended moral:** {ep['moral']['roman']} — _{ep['moral'].get('english', '')}_  ",
         f"**Attribution:** {ep.get('attribution_note', 'Original fiction.')}  ",
         f"**Music direction:** {ep.get('music', {}).get('mood', '')} (procedural tanpura drone, soft pad, sparse bells; swell at the realisation)  ",
         f"**Subtitles:** {ep.get('subtitles', 'hinglish')}  ",
         f"**Voices:** {ep.get('voices')}  "]
    if tl:
        L.append(f"**Measured runtime:** {tl['total_duration']:.2f} s  ")
    L += ["", "## Shots", ""]
    shots = tl["shots"] if tl else ep["shots"]
    for s in shots:
        hdr = f"### {s['id']} — {s.get('type', 'dialogue')} · {s.get('background', '')} · {s.get('framing', '')}"
        if tl:
            hdr += f"  ({s['start']:.1f}–{s['start'] + s['duration']:.1f} s)"
        L += [hdr, ""]
        if s.get("scene"):
            L.append(f"*Scene:* {s['scene']}  ")
        cam = s.get("camera")
        L.append(f"*Camera:* {s.get('camera_note') or _cam_text(cam, s.get('transition_in', 'cut'))}  ")
        for ln in s.get("lines", []):
            who = "MAHADEV" if ln["speaker"] == "mahadev" else "GIRL"
            vo = " (V.O.)" if ln.get("vo") else ""
            dur = f" [{ln['audio_dur']:.1f}s]" if tl else ""
            L.append(f"- **{who}{vo}** _({ln.get('emotion', 'neutral')}{', ' + ln['gesture'] if ln.get('gesture') else ''})_{dur}: "
                     f"{ln['roman']}  \n  {ln['tts']}  \n  _{ln.get('en', '')}_")
        L.append("")
    soc = ep.get("social", {})
    if soc:
        L += ["## Social", "", "**Caption:**", "", soc.get("caption", "").strip(), "", "**Hashtags:** " + " ".join(soc.get("hashtags", [])), ""]
    return "\n".join(L)


def _cam_text(cam, tr):
    if not cam:
        return f"locked-off; transition in: {tr}"
    f, t = cam.get("from", {}), cam.get("to", {})
    z0, z1 = f.get("zoom", 1.0), t.get("zoom", f.get("zoom", 1.0))
    move = "slow push-in" if z1 > z0 else "slow pull-out" if z1 < z0 else "gentle drift"
    return f"{move} ({z0:.2f}→{z1:.2f}); transition in: {tr}"


def make_storyboard(ep, log=print):
    from animation.draw import fill, font
    from animation.scene import EpisodeRenderer
    tl = resolve_timeline(ep, log=log)
    d = ROOT / "storyboards" / ep["id"]
    d.mkdir(parents=True, exist_ok=True)
    R = EpisodeRenderer(tl, TW, TH)
    n = len(tl["shots"])
    cols = 5
    rows = (n + cols - 1) // cols
    cell_h = TH + 150
    surf = skia.Surface(cols * (TW + 20) + 20, rows * (cell_h + 20) + 90)
    c = surf.getCanvas()
    c.clear(skia.Color(245, 239, 228))
    c.drawString(f"{ep['title_roman']} — storyboard ({tl['total_duration']:.1f}s)", 20, 55, font("Kalam-Bold", 40), fill("#3a2454"))
    for i, s in enumerate(tl["shots"]):
        t = s["duration"] * (0.65 if s.get("type") != "dialogue" else 0.55)
        frame = R.render(i, t)
        img = skia.Image.fromarray(np.ascontiguousarray(frame), colorType=skia.kRGBA_8888_ColorType)
        x = 20 + (i % cols) * (TW + 20)
        y = 90 + (i // cols) * (cell_h + 20)
        c.drawImage(img, x, y)
        c.drawString(f"{s['id']}  {s['start']:.1f}s +{s['duration']:.1f}s", x, y + TH + 26, font("Poppins-SemiBold", 18), fill("#222"))
        c.drawString(f"{s.get('framing', '')} · {s.get('transition_in', 'cut')}", x, y + TH + 48, font("Poppins-Regular", 15), fill("#555"))
        for k, ln in enumerate(s.get("lines", [])[:2]):
            txt = ("M: " if ln["speaker"] == "mahadev" else "G: ") + ln["roman"]
            for j, chunk in enumerate([txt[:34], txt[34:68]]):
                if chunk:
                    c.drawString(chunk, x, y + TH + 72 + k * 44 + j * 20, font("Poppins-Regular", 14), fill("#333"))
    out = d / "storyboard.png"
    surf.makeImageSnapshot().save(str(out), skia.kPNG)
    md = script_markdown(ep, tl)
    (d / "storyboard.md").write_text(md + f"\n\n![storyboard](storyboard.png)\n", encoding="utf-8")
    (Path(ep["_dir"]) / "script.md").write_text(md, encoding="utf-8")
    save_json(tl, d / "timeline.json")
    return out
