"""Download the offline models used by the pipeline into ./models (git-ignored).

    python scripts/setup_models.py                 # anime pipeline models (vocal isolation, upscaler, cut-out)
    python scripts/setup_models.py --whisper       # + offline Whisper turbo for transcribing recordings (~1 GB)
    python scripts/setup_models.py --legacy-tts    # + old Piper Hindi voices / Rhubarb

Sources (verified reachable when this repo was built):
  * Piper Hindi voices, repackaged by k2-fsa/sherpa-onnx GitHub releases (tts-models).
    Licence: CC BY-NC-SA 4.0 (pratham, priyamvada) / IIT-M IndicTTS licence (rohan) – PREVIEW USE ONLY.
  * Rhubarb Lip Sync 1.14.0 (MIT) from DanielSWolf/rhubarb-lip-sync releases.
"""
from __future__ import annotations

import platform
import shutil
import sys
import tarfile
import tempfile
import urllib.request
import zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
MODELS = ROOT / "models"
VOICES = ["hi_IN-pratham-medium", "hi_IN-priyamvada-medium", "hi_IN-rohan-medium"]
VOICE_URL = "https://github.com/k2-fsa/sherpa-onnx/releases/download/tts-models/vits-piper-{name}.tar.bz2"
RHUBARB = "https://github.com/DanielSWolf/rhubarb-lip-sync/releases/download/v1.14.0/Rhubarb-Lip-Sync-1.14.0-{os}.zip"
# Anime pipeline models (all free / open):
FILES = {
    "sep/Kim_Vocal_2.onnx": "https://github.com/TRvlvr/model_repo/releases/download/all_public_uvr_models/Kim_Vocal_2.onnx",
    "img/RealESRGAN_x4plus_anime_6B.pth": "https://github.com/xinntao/Real-ESRGAN/releases/download/v0.2.2.4/RealESRGAN_x4plus_anime_6B.pth",
    "img/isnet-anime.onnx": "https://github.com/danielgatis/rembg/releases/download/v0.0.0/isnet-anime.onnx",
}
WHISPER = "https://github.com/k2-fsa/sherpa-onnx/releases/download/asr-models/sherpa-onnx-whisper-turbo.tar.bz2"


def fetch(url, dest):
    print("downloading", url)
    with urllib.request.urlopen(url, timeout=600) as r, open(dest, "wb") as f:
        shutil.copyfileobj(r, f)


def main():
    for rel, url in FILES.items():
        dst = MODELS / rel
        dst.parent.mkdir(parents=True, exist_ok=True)
        if dst.exists():
            print("ok  ", rel)
        else:
            fetch(url, dst)
    if "--whisper" in sys.argv and not (MODELS / "asr" / "sherpa-onnx-whisper-turbo").exists():
        with tempfile.TemporaryDirectory() as td:
            arc = Path(td) / "w.tar.bz2"
            fetch(WHISPER, arc)
            (MODELS / "asr").mkdir(parents=True, exist_ok=True)
            with tarfile.open(arc) as t:
                t.extractall(MODELS / "asr", filter="data")
    if "--legacy-tts" not in sys.argv:
        print("models ready in", MODELS)
        return 0
    (MODELS / "voices").mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory() as td:
        for name in VOICES:
            target = MODELS / "voices" / f"vits-piper-{name}"
            if (target / f"{name}.onnx").exists():
                print("ok  ", name)
                continue
            arc = Path(td) / f"{name}.tar.bz2"
            fetch(VOICE_URL.format(name=name), arc)
            with tarfile.open(arc) as t:
                t.extractall(MODELS / "voices", filter="data")
        exe = MODELS / "bin" / "rhubarb" / ("rhubarb.exe" if platform.system() == "Windows" else "rhubarb")
        if exe.exists():
            print("ok   rhubarb")
        else:
            osname = {"Darwin": "macOS", "Windows": "Windows"}.get(platform.system(), "Linux")
            z = Path(td) / "rhubarb.zip"
            fetch(RHUBARB.format(os=osname), z)
            with zipfile.ZipFile(z) as zz:
                zz.extractall(td)
            src = next(Path(td).glob("Rhubarb-Lip-Sync-*"))
            shutil.copytree(src, MODELS / "bin" / "rhubarb", dirs_exist_ok=True)
            exe.chmod(0o755)
    print("models ready in", MODELS)
    return 0


if __name__ == "__main__":
    sys.exit(main())
