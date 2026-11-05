"""Create a speaker profile from an authorised voice sample and synthesise a test sentence.

    python -m voice.clone_voice --name girl --sample ~/Downloads/my_voice.wav \
        --consent private/voices/girl/consent.yaml --backend chatterbox

Steps: validate sample (incl. consent) -> copy a cleaned mono 24 kHz reference into
private/voices/<name>/ (git-ignored) -> write profile.yaml -> load backend -> generate a test
sentence -> save private/voices/<name>/test.wav.

Samples, references and generated tests never leave private/ and are never committed.
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

import soundfile as sf
import yaml

from audio.dsp import normalize_rms, resample, to_mono, trim_silence
from voice.backends import BackendUnavailable, get_backend
from voice.validate_sample import validate

ROOT = Path(__file__).resolve().parent.parent
PRIVATE = ROOT / "private" / "voices"
TEST_SENTENCE = {
    "girl": "मुझे लगता है, आज का दिन थोड़ा बेहतर होगा।",
    "mahadev": "शांत हो जाओ। हर रास्ता अपने समय पर खुलता है।",
}


def build_profile(name, sample, consent, backend, language="hi"):
    rep = validate(sample, consent)
    for w in rep.get("warnings", []):
        print("WARNING:", w)
    if not rep["ok"]:
        raise SystemExit("Sample rejected:\n  " + "\n  ".join(rep["issues"]))
    out = PRIVATE / name
    out.mkdir(parents=True, exist_ok=True)
    x, sr = sf.read(str(sample), dtype="float32")
    x = trim_silence(to_mono(x), sr)
    x = normalize_rms(resample(x, sr, 24000), -20)
    ref = out / "reference.wav"
    sf.write(ref, x, 24000)
    profile = dict(name=name, backend=backend, language=language, reference_wav=str(ref),
                   consent_file=str(Path(consent).resolve()), source_metrics=rep["metrics"])
    (out / "profile.yaml").write_text(yaml.safe_dump(profile, sort_keys=False))
    return profile


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--name", required=True, help="profile name, e.g. girl or mahadev")
    ap.add_argument("--sample", required=True)
    ap.add_argument("--consent", required=True)
    ap.add_argument("--backend", default="chatterbox", choices=["chatterbox", "xtts", "elevenlabs"])
    ap.add_argument("--allow-paid", action="store_true")
    ap.add_argument("--text", help="custom test sentence (Devanagari recommended)")
    a = ap.parse_args(argv)
    prof = build_profile(a.name, a.sample, a.consent, a.backend)
    print("profile written:", PRIVATE / a.name / "profile.yaml")
    try:
        be = get_backend(a.backend, allow_paid=a.allow_paid)
    except BackendUnavailable as e:
        print("Backend not available yet:", e)
        print("Profile is saved; install the backend and rerun to produce the test sentence.")
        return 2
    audio, sr = be.synthesize(a.text or TEST_SENTENCE.get(a.name, TEST_SENTENCE["girl"]), prof)
    test = PRIVATE / a.name / "test.wav"
    sf.write(test, audio, sr)
    print("test sentence saved:", test, "- listen to it before approving this voice.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
