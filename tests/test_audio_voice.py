import numpy as np
import pytest
import soundfile as sf
import yaml

from audio import music
from audio.dsp import SR
from audio.mix import mix
from voice.backends import MODELS
from voice.lipsync import amplitude_cues
from voice.validate_sample import validate


def test_music_score_is_clean():
    x = music.score(6.0, "night_reflective")
    assert len(x) == int(6.0 * SR)
    assert np.isfinite(x).all() and np.abs(x).max() < 1.0


def test_mix_ducks_music_under_speech():
    t = np.arange(SR * 4) / SR
    dlg = np.zeros_like(t, dtype=np.float32)
    dlg[SR:2 * SR] = 0.2 * np.sin(2 * np.pi * 220 * t[SR:2 * SR])
    st = mix(dlg, 4.0, "night_reflective")
    assert st.shape == (4 * SR, 2) and np.abs(st).max() < 1.0


def test_lipsync_closed_on_silence(tmp_path):
    x = np.zeros(SR, dtype=np.float32)
    x[SR // 2:] = 0.3 * np.sin(np.arange(SR // 2) * 2 * np.pi * 200 / SR)
    p = tmp_path / "a.wav"
    sf.write(p, x, SR)
    cues = amplitude_cues(p)
    assert cues[0]["value"] == "X" and any(c["value"] != "X" for c in cues)


def test_sample_validation_requires_consent(tmp_path):
    x = (0.1 * np.random.default_rng(0).standard_normal(SR * 12)).astype(np.float32)
    wav = tmp_path / "s.wav"
    sf.write(wav, x, SR)
    assert not validate(wav)["ok"]                        # no consent file
    c = tmp_path / "consent.yaml"
    c.write_text(yaml.safe_dump({"speaker_name": "Me", "relationship": "self", "permission_confirmed": True}))
    rep = validate(wav, c)
    assert rep["ok"], rep
    short = tmp_path / "short.wav"
    sf.write(short, x[: SR * 3], SR)
    assert not validate(short, c)["ok"]


@pytest.mark.skipif(not (MODELS / "voices" / "vits-piper-hi_IN-priyamvada-medium").exists(), reason="run scripts/setup_models.py")
def test_piper_hindi_voice_synthesises():
    from voice.backends import get_backend
    audio, sr = get_backend("piper").synthesize("नमस्ते महादेव।", {"model": "hi_IN-priyamvada-medium"})
    assert sr == 22050 and len(audio) / sr > 0.4
