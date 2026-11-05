"""Mahadev & Me production CLI.

    python -m pipeline make "Overthinking about my future"     # topic -> script -> audio -> storyboard -> reel
    python -m pipeline new "Overthinking about my future" [--outfit hoodie --location rainy_window --tone gentle]
    python -m pipeline ideas [--pillar overthinking] [--n 10]
    python -m pipeline voices episode_001                     # synthesise / cache dialogue only
    python -m pipeline storyboard episode_001
    python -m pipeline render episode_001 [--preview] [--shots s03,s05] [--jobs 4]
    python -m pipeline qa episode_001 [--preview]
    python -m pipeline assets                                  # regenerate character/background sheets
    python -m pipeline list                                    # outfits, locations, framings, expressions, voices
"""
from __future__ import annotations

import argparse
import sys


def main(argv=None):
    ap = argparse.ArgumentParser(prog="python -m pipeline", description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = ap.add_subparsers(dest="cmd", required=True)
    for name in ("make", "new"):
        p = sub.add_parser(name)
        p.add_argument("topic")
        p.add_argument("--outfit")
        p.add_argument("--location")
        p.add_argument("--tone", default="gentle", choices=["gentle", "playful", "deep"])
        p.add_argument("--pillar")
        p.add_argument("--id")
        p.add_argument("--subtitles", default="hinglish", choices=["hinglish", "hinglish+english"])
        p.add_argument("--girl-voice", default=None)
        p.add_argument("--mahadev-voice", default=None)
        p.add_argument("--llm", choices=["none", "claude"], default="none",
                       help="'claude' drafts dialogue with the Anthropic API (paid; needs ANTHROPIC_API_KEY + --allow-paid)")
        p.add_argument("--allow-paid", action="store_true")
        p.add_argument("--seed", type=int, default=None)
        if name == "make":
            p.add_argument("--preview", action="store_true")
    p = sub.add_parser("ideas")
    p.add_argument("--pillar")
    p.add_argument("--n", type=int, default=10)
    for name in ("voices", "storyboard", "render", "qa", "timeline"):
        p = sub.add_parser(name)
        p.add_argument("episode")
        p.add_argument("--preview", action="store_true")
        p.add_argument("--shots")
        p.add_argument("--jobs", type=int)
    sub.add_parser("assets")
    sub.add_parser("list")
    a = ap.parse_args(argv)

    if a.cmd == "list":
        from animation.backgrounds import BACKGROUNDS
        from animation.characters import WARDROBE
        from animation.rig import EXPRESSIONS, GESTURES
        from animation.scene import FRAMINGS
        from voice.generate_dialogue import load_voice_config
        print("outfits:    ", ", ".join(WARDROBE))
        print("locations:  ", ", ".join(BACKGROUNDS))
        print("framings:   ", ", ".join(FRAMINGS))
        print("expressions:", ", ".join(EXPRESSIONS))
        print("gestures:   ", ", ".join(GESTURES))
        print("voices:     ", ", ".join(load_voice_config()["profiles"]))
        return 0
    if a.cmd == "ideas":
        from .scriptgen import list_ideas
        for row in list_ideas(a.pillar, a.n):
            print(f"{row['id']:>3}  [{row['pillar']}]  {row['title_hinglish']}  –  {row['hook']}")
        return 0
    if a.cmd == "assets":
        from .assets import build_all
        build_all()
        return 0
    if a.cmd in ("new", "make"):
        from .scriptgen import generate_episode
        d = generate_episode(a.topic, outfit=a.outfit, location=a.location, tone=a.tone, pillar=a.pillar,
                             ep_id=a.id, subtitles=a.subtitles, girl_voice=a.girl_voice,
                             mahadev_voice=a.mahadev_voice, llm=a.llm, allow_paid=a.allow_paid, seed=a.seed)
        print("episode written:", d / "episode.yaml")
        print("script:         ", d / "script.md")
        if a.cmd == "new":
            print("Edit the YAML if you like, then: python -m pipeline render", d.name, "--preview")
            return 0
        ep_name = d.name
        return _produce(ep_name, a.preview)

    from .episode import load_episode
    ep = load_episode(a.episode)
    preset = "preview" if getattr(a, "preview", False) else "final"
    if a.cmd == "timeline":
        from .episode import resolve_timeline
        tl = resolve_timeline(ep)
        for s in tl["shots"]:
            print(f"{s['id']} {s['start']:6.2f} +{s['duration']:5.2f}  {s.get('type')}")
        print("total", tl["total_duration"])
        return 0
    if a.cmd == "voices":
        from .episode import resolve_timeline
        tl = resolve_timeline(ep)
        for s in tl["shots"]:
            for ln in s.get("lines", []):
                print(f"{ln['speaker']:8s} {ln['audio_dur']:5.2f}s  {ln['roman']}")
        print("voice profiles:", tl["voice_info"])
        return 0
    if a.cmd == "storyboard":
        from .storyboard import make_storyboard
        print(make_storyboard(ep))
        return 0
    if a.cmd == "render":
        from .render import render_episode
        shots = set(a.shots.split(",")) if a.shots else None
        render_episode(ep, preset, jobs=a.jobs, only_shots=shots)
        return 0
    if a.cmd == "qa":
        from .qa import run_qa
        rep = run_qa(ep, preset)
        return 0 if rep["passed"] else 1
    return 1


def _produce(ep_name, preview):
    from .episode import load_episode
    from .qa import run_qa_with_fixes
    from .storyboard import make_storyboard
    ep = load_episode(ep_name)
    print("storyboard:", make_storyboard(ep))
    rep = run_qa_with_fixes(ep, "preview" if preview else "final")
    return 0 if rep["passed"] else 1


if __name__ == "__main__":
    sys.exit(main())
