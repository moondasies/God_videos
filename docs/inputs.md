# Where to put your files

Everything in `private/` is git-ignored: it never goes to GitHub. The easiest way is to attach
files in the Claude chat; Claude copies them into these folders.

```
private/
├── characters/
│   └── sheet.webp | sheet.png        ← the combined character sheet (Mahadev + the Girl)
└── audio/
    └── pilot/
        ├── L01_girl_raw.(wav|m4a|mp3)     ← the girl's recording (any format ffmpeg reads)
        └── L02_mahadev_raw.(wav|m4a|mp3)  ← Mahadev's recording
```

## Character sheet
* PNG preferred (WebP/JPG fine), at least 1536×1024. The current crop coordinates in
  `anime/assets.py → REGIONS` match the 1536×1024 sheet you supplied. A redesigned sheet needs
  those boxes and face landmarks re-measured.
* Higher-resolution sheets (2–4× bigger) or separate large portraits produce sharper close-ups.

## Audio
* Any length. Background noise is cleaned automatically, and a **music bed is removed** with
  MDX-Net (Kim_Vocal_2).
* Mouth movement is generated from the voice's loudness frame by frame, so lip-sync follows
  **your** audio exactly. No timestamps are needed.
* For a new episode with several lines, name files in speaking order: `L01_girl.wav`,
  `L02_mahadev.wav`, `L03_girl.wav`… (one line per file). One continuous file also works if there
  is at least a 0.5 s pause between lines.
* Captions: the pipeline can transcribe Hindi offline with Whisper
  (`python scripts/setup_models.py --whisper`), but **check the words**. Fast speech can be
  misheard, and the pilot's captions were checked by hand against several passes.

## Permission
Use only voices you own or have written permission for. A recording that carries a music bed
(for example a clip from a TV show) belongs to that show's owners and performers. Isolating the
voice doesn't change that.
