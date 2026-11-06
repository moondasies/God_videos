# Mahadev & Me — anime/webtoon-style spiritual reels (free, offline)

The pipeline builds a 9:16 reel from **your approved character sheet** (the painted artwork is
used directly, not redrawn) and **your own voice recordings**. Everything runs on CPU with free,
open models. There are no paid APIs and no API keys.

```bash
python -m anime.pilot             # 1080x1920 @30fps final  (~2 min on 4 CPU cores)
python -m anime.pilot --preview   # 540x960 quick check     (~1 min)
```

Output: `outputs/pilot_v2/pilot_v2.mp4` (+ `pilot_v2_hinglish.srt`, `plan.json`).

## Pilot v2 (current)

| | |
|---|---|
| File | `outputs/pilot_v2/pilot_v2.mp4` |
| Duration | 32.17 s |
| Format | 1080×1920, 30 fps, H.264 High + AAC 48 kHz, −14.4 LUFS, peak −1.5 dBFS |
| Voices | your two recordings: the girl ("Mera naam Srijita hai, main 22 saal ki hoon…") and Mahadev ("Jo bhi meri pooja karega, use pariksha to deni hogi") |
| Girl's outfit | changed to a **dusty-rose blazer** (recolour of the sheet's beige plaid blazer; face, hair, jewellery untouched) |
| Shots | 12: establishing → girl medium → moon cutaway → girl close-up → dreamy cutaway → girl → Mahadev's glow entrance → Mahadev medium → close-up → girl's surprised reaction → two-shot → quote end card |

## How it works (all free)

| Stage | Tool | Licence |
|---|---|---|
| Upscale sheet art ×4 | Real-ESRGAN x4plus **anime** 6B (`anime/upscale.py`) | BSD-3 |
| Cut characters out | ISNet-**anime** via rembg (`anime/assets.py`) | Apache-2.0 / MIT |
| Outfit change | colour recolour of the jacket mask, preserving shading and weave | – |
| Remove music/noise from voice | UVR MDX-Net **Kim_Vocal_2** (`anime/separate.py`) + ffmpeg denoise | MIT (UVR models) |
| Life motion | `anime/puppet.py`: smooth displacement-field warp (head sway, nods, breathing, hair sway), painted blinks, anime mouth shapes driven by the voice's loudness each frame | – |
| Cinematics | `anime/pilot.py`: defocused background plates, glow, floating particles, vignette, push-ins, whip-pan "swoosh" cuts, glow-flash entrance | – |
| Captions / titles | skia + Poppins / Kalam / Yatra One (SIL OFL) | OFL |
| Music | procedural, original (`audio/music.py`), ducked under speech | – |

Setup:

```bash
python3 -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
python scripts/setup_models.py             # ~260 MB of free models from GitHub releases
python -m pytest -q
```

Put your inputs in `private/` as described in **docs/inputs.md**.

## Honest limitations
* **Mouth movement is painted over the still artwork**, so it works best on the two large portraits.
  The small expression heads, full-body figures and cutaways don't lip-sync; the edit only uses
  them for reactions, voice-over and wide shots.
* **Motion is subtle 2.5D** (warping a single painting), like the reference reel. It is not
  frame-by-frame animation, and there are no new poses or angles beyond what the sheet contains.
* **The outfit change is a recolour.** The garment's cut stays the sheet's blazer; a completely
  different garment needs new art on the sheet.
* **Backgrounds** are original procedural plates shown out of focus. Painted backgrounds can be
  dropped in later.
* **Mahadev's recording** contained a music bed, which suggests it comes from a show or video. Only
  publish it if you have the rights; otherwise record a consenting voice.

The previous flat vector-puppet pipeline was removed. It is still in git history (commit `5223d67`).
