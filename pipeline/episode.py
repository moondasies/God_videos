"""Episode files (YAML) -> validated dict -> resolved timeline (with real audio timings)."""
from __future__ import annotations

import copy
import json
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parent.parent
TARGET_MIN, TARGET_MAX = 30.0, 40.0

SHOT_TYPES = {"dialogue", "insert_phone_feed", "insert_phone_chat", "metaphor_flowers", "moral"}


class EpisodeError(ValueError):
    pass


def episode_dir(ep_ref) -> Path:
    p = Path(ep_ref)
    if p.suffix in (".yaml", ".yml"):
        return p.parent
    if not p.exists():
        p = ROOT / "episodes" / str(ep_ref)
    return p


def load_episode(ep_ref):
    d = episode_dir(ep_ref)
    f = d / "episode.yaml"
    if not f.exists():
        raise EpisodeError(f"no episode.yaml in {d}")
    ep = yaml.safe_load(f.read_text(encoding="utf-8"))
    ep["_dir"] = str(d)
    validate_episode(ep)
    return ep


def validate_episode(ep):
    from animation.backgrounds import BACKGROUNDS
    from animation.characters import WARDROBE
    from animation.scene import FRAMINGS
    errs = []
    for k in ("id", "title_roman", "moral", "shots", "voices"):
        if k not in ep:
            errs.append(f"missing key: {k}")
    out = ep.get("characters", {}).get("girl", {}).get("outfit")
    if out and out not in WARDROBE:
        errs.append(f"unknown outfit {out}; choose from {sorted(WARDROBE)}")
    ids = set()
    for s in ep.get("shots", []):
        sid = s.get("id")
        if sid in ids:
            errs.append(f"duplicate shot id {sid}")
        ids.add(sid)
        if s.get("type", "dialogue") not in SHOT_TYPES:
            errs.append(f"{sid}: unknown type {s.get('type')}")
        if s.get("background") and s["background"] not in BACKGROUNDS:
            errs.append(f"{sid}: unknown background {s['background']}")
        if s.get("framing") and s["framing"] not in FRAMINGS:
            errs.append(f"{sid}: unknown framing {s['framing']}")
        for a in s.get("actors", {}).values():
            if a.get("outfit") and a["outfit"] not in WARDROBE:
                errs.append(f"{sid}: unknown outfit {a['outfit']}")
        for ln in s.get("lines", []):
            for k in ("speaker", "roman", "tts"):
                if not ln.get(k):
                    errs.append(f"{sid}: line missing {k}")
            if ln.get("speaker") not in ("girl", "mahadev"):
                errs.append(f"{sid}: unknown speaker {ln.get('speaker')}")
            if ln.get("attribution") == "scripture" and not ln.get("source"):
                errs.append(f"{sid}: scripture-attributed line needs a `source` citation")
    if errs:
        raise EpisodeError("; ".join(errs))


def resolve_timeline(ep, allow_paid=False, log=print):
    """Synthesise every line (cached), lay out shots, auto-fit to 30-40 s."""
    from voice.generate_dialogue import load_voice_config, resolve_profile, synth_line
    cfg = load_voice_config()
    tl = copy.deepcopy(ep)
    voice_info = {}
    for shot in tl["shots"]:
        for ln in shot.get("lines", []):
            prof = resolve_profile(cfg, ep["voices"][ln["speaker"]])
            m = synth_line(ln["tts"], prof, ln.get("emotion", "neutral"), allow_paid=allow_paid)
            ln.update(wav=m["wav"], audio_dur=m["duration"], cues=m["cues"], lipsync=m["lipsync_method"])
            voice_info[ln["speaker"]] = dict(profile=prof["profile_name"], backend=prof["backend"],
                                             preview=bool(prof.get("preview")), license=prof.get("license", ""))
    tl["voice_info"] = voice_info

    def layout(pause_k=1.0, moral_dur=None):
        t_global = 0.0
        for shot in tl["shots"]:
            t = shot.get("lead_in", 0.3)
            for ln in shot.get("lines", []):
                t += ln.get("delay", 0.0)
                ln["t0"] = round(t, 3)
                ln["t1"] = round(t + ln["audio_dur"], 3)
                t = ln["t1"] + max(0.15, ln.get("pause_after", 0.42) * pause_k)
            dur = max(shot.get("min_duration", 0.0), t - (0.0 if not shot.get("lines") else max(0.15, 0.42 * pause_k))
                      + shot.get("tail", 0.35))
            if shot.get("type") == "moral" and moral_dur:
                dur = moral_dur
            shot["duration"] = round(dur, 3)
            shot["start"] = round(t_global, 3)
            t_global += dur
        return t_global

    total = layout()
    moral = next((s for s in tl["shots"] if s.get("type") == "moral"), None)
    if total > TARGET_MAX - 0.3:
        for k in (0.8, 0.6, 0.45, 0.35):
            total = layout(k, 3.2 if moral else None)
            if total <= TARGET_MAX - 0.3:
                break
    elif total < TARGET_MIN + 0.5:
        for md in (5.0, 6.0, 7.0):
            total = layout(1.3, md if moral else None)
            if total >= TARGET_MIN + 0.5:
                break
    tl["total_duration"] = round(total, 3)
    if not (TARGET_MIN <= total <= TARGET_MAX):
        log(f"WARNING: duration {total:.2f}s outside {TARGET_MIN}-{TARGET_MAX}s – shorten/lengthen the script")
    # music swell + audio events in global time
    sw = next((s["start"] for s in tl["shots"] if s.get("music_swell")), None)
    tl["music_swell_at"] = sw
    sfx = []
    amb = []
    from animation.backgrounds import get_background
    for s in tl["shots"]:
        for e in s.get("sfx", []):
            sfx.append((e["type"], s["start"] + e.get("at", 0.0)))
        if s.get("type") in ("dialogue", "insert_phone_feed", "insert_phone_chat") and s.get("background"):
            kind = get_background(s["background"]).get("ambient")
            if amb and amb[-1][0] == kind and abs(amb[-1][2] - s["start"]) < 1e-3:
                amb[-1] = (kind, amb[-1][1], s["start"] + s["duration"])
            else:
                amb.append((kind, s["start"], s["start"] + s["duration"]))
        for ln in s.get("lines", []):
            ln["g0"] = round(s["start"] + ln["t0"], 3)
            ln["g1"] = round(s["start"] + ln["t1"], 3)
    tl["sfx_events"] = sfx
    tl["ambient"] = amb
    return tl


def save_json(obj, path):
    Path(path).parent.mkdir(parents=True, exist_ok=True)
    Path(path).write_text(json.dumps(obj, indent=1, ensure_ascii=False), encoding="utf-8")
