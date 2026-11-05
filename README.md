# Mahadev & Me — AI-assisted animated spiritual reels

An offline, CPU-only pipeline that turns a topic into a finished **9:16, 1080×1920, 30–40 s
H.264/AAC** animated reel in **Hinglish**. A modern young woman talks with **Mahadev**, who helps
her see one modern-life problem differently.

```bash
python -m pipeline make "Overthinking about my future"
```

That one command writes the script, storyboard, voices, lip-synced animation, captions, music,
final MP4 and QA report.

## Sample reels

| Reel | File | Duration | Resolution | Voices | QA |
|---|---|---|---|---|---|
| EP1 "Main kabhi kaafi kyun nahi hoti?" (comparison, self-worth) | `outputs/episode_001/episode_001.mp4` | 39.05 s | 1080×1920 @30 fps, H.264 High + AAC 48 kHz | **PREVIEW** (Piper Hindi) | passed (2 voice warnings) |
| EP2 "Log humein hurt kyun karte hain?" (betrayal, boundaries) | `outputs/episode_002/episode_002.mp4` | 39.93 s | same | **PREVIEW** | passed (2 voice warnings) |
| EP3 "Dimaag chup kyun nahi hota?" (auto-generated from the topic, unedited) | `outputs/episode_003/episode_003.mp4` | 32.23 s | same | **PREVIEW** | passed (2 voice warnings) |

Each episode folder contains `qa_report.md`, Hinglish and English `.srt` files, `episode.yaml` and
`script.md`. Storyboards are in `storyboards/<ep>/`.

**These are preview-quality productions, not final channel content:**
* The voices are temporary Piper Hindi voices licensed CC BY-NC-SA 4.0, so they are **not usable on
  a monetised channel**. Replace them with your cloned voice and an authorised Mahadev voice
  (`docs/voice_setup.md`).
* The characters are a **stylised vector interpretation** of the illustrated sheet. They are not the
  painted look, and you should approve or adjust the face (`docs/character_bible.md`).
* The rig is upper-body only (no legs or walking). Three-quarter views are used rather than true
  side profiles.

## Setup

```bash
git clone https://github.com/moondasies/God_videos && cd God_videos
python3 -m venv .venv && source .venv/bin/activate      # Windows: .venv\Scripts\activate
pip install -r requirements.txt
python scripts/setup_models.py                           # Hindi Piper voices + Rhubarb lip-sync (about 200 MB)
python -m pytest -q                                      # 24 tests
python -m pipeline render episode_001 --preview          # about 30 s on a 4-core laptop
```

System requirement: **ffmpeg** with `libx264` and `rubberband` (Ubuntu: `apt install ffmpeg`;
macOS: `brew install ffmpeg`; Windows: a full ffmpeg build on PATH). On minimal Linux images,
skia also needs `libegl1` (`apt install libegl1`).

## Repository layout

```
animation/   rig.py (2.5D face, visemes, IK, hands) · characters.py (locked identities + wardrobe)
             backgrounds.py (12 procedural locations) · props.py (phone inserts, flowers) · scene.py (renderer, captions)
audio/       dsp.py · music.py (procedural score / ambience / SFX) · mix.py (ducking mix)
voice/       backends.py (piper | chatterbox | xtts | elevenlabs) · validate_sample.py · clone_voice.py
             generate_dialogue.py · lipsync.py · voice_config.example.yaml
pipeline/    __main__.py (CLI) · episode.py (YAML + timeline) · render.py · qa.py · storyboard.py · scriptgen.py · assets.py
episodes/    episode_00N/episode.yaml + script.md
assets/      characters/{girl,mahadev}/*.png (reference sheets, transparent poses) · backgrounds/ · fonts/ (SIL OFL)
research/    channel reports (access-limited, see below) · 50_original_reel_ideas.csv · analyze_reels.py
docs/        channel_identity_style_guide.md · character_bible.md · voice_setup.md · pipeline.md
config/      voices.yaml · identity.lock.json
private/     (git-ignored) your photo, character sheet, voice samples, consent files, cloned profiles
models/ cache/  (git-ignored) downloaded weights, per-line audio and per-shot video caches
```

## Research status
Instagram, YouTube and the article pages were **blocked by the network policy of the
environment this was built in**, so **no reels from either inspiration channel were watched**.
`research/channel_*_analysis.md` records exactly what was attempted. For `@godspov_`, it also
records what search snippets say ("Gods POV": an animated, conversational Krishna; YouTube
`@Gods_pov`). `research/analyze_reels.py` measures reels you save locally, so the analysis can be
completed from real data.

## Safety and honesty rules built in
* Every line carries `attribution: original_fiction`. Scripture-style claims without a `source`
  fail QA.
* Heavy topics get a help-seeking note (Tele-MANAS 14416) in the caption and attribution note.
* Voice cloning requires a signed `consent.yaml`. Samples never leave `private/`.
* Paid services (Claude script drafting, ElevenLabs) are off unless explicitly enabled.

See `docs/pipeline.md` for the full CLI, YAML schema, caching and automation status.
