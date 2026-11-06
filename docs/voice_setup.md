# Voice setup

> **Status (pilot v2):** the pilot uses your own recordings directly (`docs/inputs.md`). The Piper preview voices below are kept only as an optional, legacy tool.


Two recurring voices: **the girl** (your own voice) and **Mahadev** (a separately licensed or
authorised voice). Until those are approved, episodes use **preview voices**, which QA flags as
`WARN – PREVIEW voice`.

## 1. Current state (verified in the build container: Linux x86-64, 4 CPU, no GPU)

| Profile | Backend | Model | Status | Licence |
|---|---|---|---|---|
| `girl_preview` | Piper (ONNX, CPU) | `hi_IN-priyamvada-medium` | **tested**, used in sample reels | CC BY-NC-SA 4.0: **non-commercial preview only** |
| `mahadev_preview` | Piper + rubberband pitch −0.6 st + warmth + light room | `hi_IN-pratham-medium` | **tested**, used in sample reels | CC BY-NC-SA 4.0: **non-commercial preview only** |
| `girl_clone` / `mahadev_clone` | Chatterbox Multilingual (MIT) | your reference WAV | code path written, **not tested here** (model host blocked) | MIT (code + weights); you must own or have permission for the voice |
| XTTS-v2 via `coqui-tts` | maintained Coqui fork | reference WAV | code path written, **not tested here** | Coqui Public Model Licence: **non-commercial** |
| `mahadev_elevenlabs` | ElevenLabs API | licensed voice id | disabled until you approve the cost (`allow_paid`) | paid commercial |

Measured preview synthesis speed on CPU: about 0.3 s per line. The Mahadev preview's median pitch
is about 105 Hz before the shift; the girl's is about 230 Hz.

**Why not the old `TTS` package?** It's unmaintained. Use `coqui-tts` (the maintained fork) if
you want XTTS.

**Hindi and Hinglish caveat.** The TTS reads the **Devanagari** `tts:` field of each line.
English loan-words are transliterated, e.g. "ग्रोथ", "टाइमलाइन", "ट्रस्ट". Roman Hinglish is
used only for captions. No model available here was verified to handle Roman-script
code-switching correctly, so don't feed Roman Hinglish to TTS.

## 2. Recording your samples

* Quiet, soft-furnished room. Phone 20–30 cm from your mouth. No music, fan or AC.
* WAV, 44.1 or 48 kHz, mono. Peaks around −6 dBFS, with **no clipping**.
* About 10 s is enough for a first experiment. **30–120 s** of varied, natural Hindi and Hinglish
  speech (calm, happy, sad, questioning) gives much more stable results.
* Short recordings won't give studio-quality cloning. Expect some accent and prosody drift and
  listen to every line.

## 3. Consent file (required)

Create `private/voices/<name>/consent.yaml`. The `private/` folder is git-ignored.

```yaml
speaker_name: "Your Name"
relationship: self            # self | licensed | commissioned
permission_confirmed: true
scope: "Mahadev & Me channel – synthetic dialogue for animated reels"
date: 2026-11-05
```

For Mahadev, the voice owner signs. Never use a voice extracted from someone's videos without their
permission. If you don't have one, keep `mahadev_preview` for previews and choose a
**commercially licensed synthetic voice** (for example an ElevenLabs library voice, after you
approve the cost), or record a consenting voice artist.

## 4. Commands

```bash
# validate a sample (duration, sample rate, clipping, SNR estimate, silence ratio + consent)
python -m voice.validate_sample private/voices/girl/sample.wav --consent private/voices/girl/consent.yaml

# create the profile + synthesise a test sentence (Chatterbox recommended)
pip install chatterbox-tts        # plus a torch build for your platform (CUDA if you have an NVIDIA GPU)
python -m voice.clone_voice --name girl --sample private/voices/girl/sample.wav \
       --consent private/voices/girl/consent.yaml --backend chatterbox

# quick line test with any configured profile
python -m voice.generate_dialogue --say mahadev "शांत हो जाओ।"

# generate / cache all dialogue for an episode
python -m voice.generate_dialogue episode_001
```

Then switch the episode to the approved voices:

```yaml
voices: {girl: girl_clone, mahadev: mahadev_clone}
```

Re-render the episode. Only the changed audio lines and the shots they drive are regenerated.

## 5. Low-spec laptops

Piper preview voices run on any CPU. Chatterbox and XTTS on CPU work but are slow (often slower
than real time). Options: a free or cheap GPU notebook, or a cloud GPU you approve. Generated WAVs
are cached in `cache/voice/`, so each line is synthesised only once.

## 6. What the dialogue system does

1. Validates that the sample exists. 2. Checks consent. 3. Checks audio quality. 4. Loads the
backend. 5. Generates a test sentence. 6. Saves it. 7. Keeps separate speaker profiles
(`config/voices.yaml`). 8. Generates each dialogue line separately, using emotion → pace, gain and
pitch tweaks. 9. Inserts natural pauses (per-line `pause_after`, auto-fitted to the 30–40 s target).
10. Exports a synchronised dialogue track (`outputs/<ep>/stem_dialogue.wav`) plus mouth cues.
