"""TTS / voice-cloning backends behind one interface.

Backend status (as verified in this repository's CI-less dev container, CPU only):

| backend     | cloning | Hindi | licence of weights                 | status here            |
|-------------|---------|-------|------------------------------------|------------------------|
| piper       | no      | yes   | CC BY-NC-SA 4.0 (hi_IN voices)      | TESTED – preview voices |
| xtts        | yes     | yes   | Coqui Public Model Licence (NC)    | code path, NOT tested  |
| chatterbox  | yes     | yes   | MIT (multilingual model)           | code path, NOT tested  |
| elevenlabs  | yes     | yes   | paid commercial API                | disabled unless allowed |

Every backend returns (float32 mono numpy array, sample_rate).
"""
from __future__ import annotations

import os
import shutil
import subprocess
import tempfile
from pathlib import Path

import numpy as np
import soundfile as sf

ROOT = Path(__file__).resolve().parent.parent
MODELS = ROOT / "models"

# Emotion -> delivery tweaks (speed multiplier >1 = slower, gain, pitch in semitones)
EMOTION_DELIVERY = {
    "neutral": dict(length=1.0, gain=1.0, pitch=0.0),
    "sad": dict(length=1.12, gain=0.86, pitch=-0.4),
    "hurt": dict(length=1.12, gain=0.86, pitch=-0.3),
    "disappointed": dict(length=1.08, gain=0.88, pitch=-0.3),
    "worried": dict(length=1.0, gain=0.95, pitch=0.2),
    "frustrated": dict(length=0.95, gain=1.05, pitch=0.2),
    "curious": dict(length=1.0, gain=1.0, pitch=0.4),
    "thoughtful": dict(length=1.08, gain=0.95, pitch=0.0),
    "hopeful": dict(length=1.0, gain=1.0, pitch=0.3),
    "smile": dict(length=0.97, gain=1.02, pitch=0.4),
    "laugh": dict(length=0.95, gain=1.05, pitch=0.6),
    "calm": dict(length=1.05, gain=1.0, pitch=0.0),
    "compassionate": dict(length=1.08, gain=0.97, pitch=0.0),
    "playful": dict(length=0.98, gain=1.02, pitch=0.3),
    "peaceful": dict(length=1.1, gain=0.95, pitch=0.0),
    "surprised": dict(length=0.95, gain=1.05, pitch=0.8),
}


class BackendUnavailable(RuntimeError):
    pass


def _ffmpeg_pitch(audio, sr, semitones):
    """Formant-preserving-ish pitch shift via ffmpeg rubberband (no duration change)."""
    if abs(semitones) < 0.05 or not shutil.which("ffmpeg"):
        return audio
    ratio = 2 ** (semitones / 12)
    with tempfile.TemporaryDirectory() as td:
        a, b = Path(td) / "a.wav", Path(td) / "b.wav"
        sf.write(a, audio, sr)
        r = subprocess.run(["ffmpeg", "-y", "-loglevel", "error", "-i", str(a), "-af",
                            f"rubberband=pitch={ratio:.5f}:formant=preserved", str(b)],
                           capture_output=True)
        if r.returncode != 0:
            return audio
        out, _ = sf.read(b, dtype="float32")
    return out


class PiperBackend:
    """Offline Piper VITS voices (ONNX). Hindi voices: pratham (male), priyamvada (female), rohan (male).

    Input text must be Devanagari for correct Hindi pronunciation (espeak-ng 'hi' frontend);
    English loan-words should be transliterated (e.g. 'टाइमलाइन').
    """
    name = "piper"

    def __init__(self):
        try:
            from piper import PiperVoice  # noqa: F401
        except ImportError as e:  # pragma: no cover
            raise BackendUnavailable("pip install piper-tts") from e
        self._voices = {}

    def _voice(self, model):
        from piper import PiperVoice
        if model not in self._voices:
            path = MODELS / "voices" / f"vits-piper-{model}" / f"{model}.onnx"
            if not path.exists():
                raise BackendUnavailable(f"Piper model missing: {path}. Run: python scripts/setup_models.py")
            self._voices[model] = PiperVoice.load(str(path))
        return self._voices[model]

    def synthesize(self, text, profile, emotion="neutral"):
        from piper import SynthesisConfig
        d = EMOTION_DELIVERY.get(emotion, EMOTION_DELIVERY["neutral"])
        v = self._voice(profile["model"])
        cfg = SynthesisConfig(length_scale=profile.get("length_scale", 1.0) * d["length"],
                              noise_scale=profile.get("noise_scale", 0.667),
                              noise_w_scale=profile.get("noise_w", 0.8))
        chunks = list(v.synthesize(text, cfg))
        if not chunks:
            raise RuntimeError(f"Piper produced no audio for: {text!r}")
        audio = np.concatenate([c.audio_float_array for c in chunks]).astype(np.float32)
        sr = chunks[0].sample_rate
        audio = _ffmpeg_pitch(audio, sr, profile.get("pitch_semitones", 0.0) + d["pitch"])
        return audio * d["gain"], sr


class XTTSBackend:
    """Coqui XTTS-v2 via the maintained `coqui-tts` fork (NOT the abandoned `TTS` package).

    Clones from a reference WAV. Supports language 'hi'. Weights are under the Coqui Public
    Model Licence (non-commercial) – fine for experiments, NOT for a monetised channel.
    Untested in this repo's container (model download host was blocked).
    """
    name = "xtts"

    def __init__(self):
        try:
            from TTS.api import TTS  # provided by `pip install coqui-tts`
        except ImportError as e:
            raise BackendUnavailable("pip install coqui-tts  (and torch for your platform)") from e
        os.environ.setdefault("COQUI_TOS_AGREED", "0")
        self._tts = TTS("tts_models/multilingual/multi-dataset/xtts_v2")

    def synthesize(self, text, profile, emotion="neutral"):
        ref = Path(profile["reference_wav"])
        if not ref.exists():
            raise BackendUnavailable(f"reference sample missing: {ref}")
        d = EMOTION_DELIVERY.get(emotion, EMOTION_DELIVERY["neutral"])
        wav = self._tts.tts(text=text, speaker_wav=str(ref), language=profile.get("language", "hi"),
                            speed=1.0 / d["length"])
        return np.asarray(wav, dtype=np.float32) * d["gain"], 24000


class ChatterboxBackend:
    """Resemble AI Chatterbox Multilingual (MIT licence) – zero-shot cloning incl. Hindi.

    Recommended route for cloning YOUR voice for a commercial channel. Untested here.
    """
    name = "chatterbox"

    def __init__(self):
        try:
            from chatterbox.mtl_tts import ChatterboxMultilingualTTS
        except ImportError as e:
            raise BackendUnavailable("pip install chatterbox-tts") from e
        import torch
        dev = "cuda" if torch.cuda.is_available() else "cpu"
        self._m = ChatterboxMultilingualTTS.from_pretrained(device=dev)

    def synthesize(self, text, profile, emotion="neutral"):
        d = EMOTION_DELIVERY.get(emotion, EMOTION_DELIVERY["neutral"])
        exag = {"sad": 0.4, "hurt": 0.45, "laugh": 0.8, "frustrated": 0.7, "surprised": 0.75}.get(emotion, 0.5)
        wav = self._m.generate(text, language_id=profile.get("language", "hi"),
                               audio_prompt_path=str(profile["reference_wav"]), exaggeration=exag)
        return wav.squeeze().cpu().numpy().astype(np.float32) * d["gain"], self._m.sr


class ElevenLabsBackend:
    """Paid API. Refuses to run unless config sets allow_paid: true AND ELEVENLABS_API_KEY is set."""
    name = "elevenlabs"

    def __init__(self, allow_paid=False):
        if not allow_paid:
            raise BackendUnavailable("ElevenLabs is a paid service: set allow_paid: true in config/voices.yaml "
                                     "only after you approve the cost.")
        if not os.environ.get("ELEVENLABS_API_KEY"):
            raise BackendUnavailable("ELEVENLABS_API_KEY not set (see .env.example)")

    def synthesize(self, text, profile, emotion="neutral"):  # pragma: no cover - network
        import json
        import urllib.request
        url = f"https://api.elevenlabs.io/v1/text-to-speech/{profile['voice_id']}?output_format=pcm_24000"
        body = json.dumps({"text": text, "model_id": profile.get("model_id", "eleven_multilingual_v2")}).encode()
        req = urllib.request.Request(url, data=body, headers={"xi-api-key": os.environ["ELEVENLABS_API_KEY"],
                                                              "Content-Type": "application/json"})
        pcm = urllib.request.urlopen(req, timeout=120).read()
        return np.frombuffer(pcm, dtype="<i2").astype(np.float32) / 32768.0, 24000


_BACKENDS = {}


def get_backend(name, allow_paid=False):
    if name not in _BACKENDS:
        cls = {"piper": PiperBackend, "xtts": XTTSBackend, "chatterbox": ChatterboxBackend}.get(name)
        if name == "elevenlabs":
            _BACKENDS[name] = ElevenLabsBackend(allow_paid=allow_paid)
        elif cls is None:
            raise BackendUnavailable(f"unknown backend {name}")
        else:
            _BACKENDS[name] = cls()
    return _BACKENDS[name]
