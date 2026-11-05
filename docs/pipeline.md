# Production pipeline

```
topic ─▶ script (templates | optional Claude) ─▶ episode.yaml (editable)
      ─▶ voices (per line, cached) ─▶ mouth cues (energy + Rhubarb hybrid)
      ─▶ timeline (audio-driven, auto-fit to 30–40 s)
      ─▶ storyboard (keyframes + screenplay)
      ─▶ audio mix (dialogue + procedural score + ambience + SFX, ducked, −14 LUFS)
      ─▶ per-shot video segments (parallel, cached by content hash)
      ─▶ concat + mux (H.264 / AAC) ─▶ QA report (+ auto-fix) ─▶ final MP4 + SRTs
```

## Everyday use

```bash
python -m pipeline list                                   # outfits, locations, framings, expressions, gestures, voices
python -m pipeline ideas --pillar overthinking            # browse the 50-idea bank
python -m pipeline new "Overthinking about my future" --outfit hoodie --location rainy_window --tone playful
#   -> episodes/episode_00N/episode.yaml + script.md   (edit freely)
python -m pipeline storyboard episode_00N                 # storyboards/episode_00N/storyboard.png + .md
python -m pipeline render episode_00N --preview           # 540x960 @24fps (about 30 s on 4 CPU cores)
python -m pipeline render episode_00N                     # 1080x1920 @30fps final (about 5 min on 4 CPU cores)
python -m pipeline qa episode_00N                         # outputs/episode_00N/qa_report.md
python -m pipeline make "Fear of disappointing my parents" # all of the above in one go (final + QA + auto-fix)
python -m pipeline render episode_001 --shots s05         # force-rebuild one shot; others come from cache
```

## Episode YAML cheat-sheet

```yaml
characters: {girl: {outfit: hoodie}}           # wardrobe key (python -m pipeline list)
voices: {girl: girl_preview, mahadev: mahadev_preview}
music: {mood: night_reflective}                # night_reflective | sunset_tender | dream | hopeful
subtitles: hinglish                            # or hinglish+english
shots:
  - id: s03
    type: dialogue                             # dialogue | insert_phone_feed | insert_phone_chat | metaphor_flowers | moral
    background: bedroom_night                  # 12 procedural locations
    framing: two_shot                          # two_shot | closeup_girl | closeup_mahadev | medium_* | back_wide | empty
    transition_in: glow                        # cut | dissolve | glow | fade
    camera: {from: {zoom: 1.08, x: 600}, to: {zoom: 1.0}}
    sfx: [{type: divine_shimmer, at: 0.0}]
    actors:
      mahadev: {appear: {at: 0.1, dur: 1.3}, expr: compassionate, gesture: lap, props: {trishul: true}}
      girl: {expr: surprised, expr_keys: [[1.6, curious]], yaw: 0.4, look: [0.3, 0]}
    lines:
      - speaker: mahadev
        emotion: compassionate                 # drives face + voice delivery
        gesture: explain                       # explain | abhaya | heart | chin | point_up | shrug | ...
        roman: "Tumhe kisne kaha..."           # caption (Roman Hinglish)
        tts: "तुम्हें किसने कहा..."              # spoken text (Devanagari)
        en: "Who told you..."                  # optional English subtitle
        attribution: original_fiction          # or scripture + source: "<citation>"
        listener_emotion: curious
        pause_after: 0.4
```

## Caching and regeneration
* `cache/voice/<hash>.wav|json`: one file per (text, voice profile, emotion). Editing one line
  re-synthesises only that line.
* `cache/segments/<ep>_<shot>_<preset>_<hash>.mp4`: the hash covers the shot spec, line timings,
  neighbouring-shot data for dissolves, and the renderer source code. Unchanged shots are reused.

## Automation status

| Stage | Automated? | Paid? | Needs approval? |
|---|---|---|---|
| Topic → script (templates) | yes | no | **review recommended** before publishing |
| Topic → script (Claude) | yes (`--llm claude --allow-paid`) | **yes** (Anthropic API) | yes: cost, then review |
| Storyboard / screenplay | yes | no | no |
| Preview voices (Piper) | yes | no | non-commercial licence: not for monetised posts |
| Your cloned voices | yes once a profile exists | no (Chatterbox local) / **yes** (ElevenLabs) | **yes**: consent file + listen test |
| Lip-sync, animation, captions, music, mix | yes | no | no |
| QA + auto-fix (music level) | yes | no | no |
| Publishing to Instagram / YouTube | **not implemented** | – | always manual |

## Hardware
Everything runs on CPU. Measured in the build container (4 vCPU, 15 GB RAM, no GPU): a preview
reel takes about 30 s, a final 1080p reel about 5 min, and RAM use stays under 1.5 GB. GPU is
only useful for the optional neural cloning backends.

## Upgrade paths (not built)
* **Painted look:** replace the vector face and body drawing with layered PNG parts generated from
  the character sheet (eyes, mouths, brows as separate layers) behind the same `Character.draw()`
  interface. The rig, lip-sync and timing keep working.
* **Generative video:** image-to-video tools can add richer motion to inserts or establishing shots.
  They don't yet keep character identity stable across shots, so keep the rig for dialogue.
* **Full-body poses and walking:** extend the rig with legs and IK.
