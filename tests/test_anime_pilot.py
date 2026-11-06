import numpy as np
import pytest

from anime.assets import OUTFITS, recolour
from anime.pilot import SR, _tighten_pauses, caption_chunks, mouth_envelope
from anime.puppet import PaintedActor
from anime.separate import MODEL as SEP_MODEL


def _fake_portrait():
    h, w = 400, 320
    img = np.zeros((h, w, 4), np.uint8)
    img[..., :3] = (230, 190, 160)
    img[60:160, 60:260, :3] = (40, 25, 20)      # hair
    img[260:, :, :3] = (200, 190, 175)          # beige jacket
    img[..., 3] = 255
    meta = {"eyes": [[120, 150, 20], [200, 150, 20]], "mouth": [160, 220, 30, 0.0], "pivot": [160, 300],
            "chin_y": 260, "skin_probe": [160, 190], "lip": [160, 224]}
    return img, meta


def test_puppet_moves_blinks_and_talks():
    img, meta = _fake_portrait()
    a = PaintedActor(img, meta, "girl")
    f0 = a.frame(0.0)
    f1 = a.frame(1.3)
    talk = a.frame(0.0, mouth_open=1.0)
    blink = a.frame(0.0, blink=1.0)
    assert f0.shape == (400, 320, 4)
    assert np.abs(f0 - f1).mean() > 1e-4                       # organic motion over time
    assert talk[210:240, 140:180, :3].min() < f0[210:240, 140:180, :3].min() - 0.3   # dark open mouth
    assert np.abs(blink[135:165, 100:140] - f0[135:165, 100:140]).mean() > 0.01         # lids painted


def test_outfit_recolour_changes_only_jacket():
    img, _ = _fake_portrait()
    alpha = np.ones(img.shape[:2], np.float32)
    out, m = recolour(img[..., :3], alpha, OUTFITS["rose_blazer"]["hue"], top_y=250)
    assert m[300:, :].mean() > 0.8 and m[:200, :].mean() < 0.05
    assert out[350, 160, 0] != img[350, 160, 0] or out[350, 160, 1] != img[350, 160, 1]


def test_mouth_envelope_tracks_voice():
    t = np.arange(SR * 2) / SR
    x = np.zeros_like(t, dtype=np.float32)
    x[SR // 2:SR] = 0.3 * np.sin(2 * np.pi * 180 * t[SR // 2:SR])
    env = mouth_envelope(x, 30)
    assert env[:10].max() < 0.05 and env[20:28].mean() > 0.4 and env[45:].max() < 0.2


def test_pause_tightening_and_captions():
    x = np.concatenate([np.ones(SR) * 0.3, np.zeros(SR * 2), np.ones(SR) * 0.3]).astype(np.float32)
    y = _tighten_pauses(x, 0.5)
    assert abs(len(y) / SR - 2.5) < 0.1
    ch = caption_chunks("Mera naam Srijita hai, main 22 saal ki hoon, aur mujhe", 0.0, 4.0)
    assert ch[0][0] == 0.0 and abs(ch[-1][1] - 4.0) < 1e-6
    assert all(len(" ".join(w)) <= 26 for _, _, w in ch)


@pytest.mark.skipif(not SEP_MODEL.exists(), reason="run scripts/setup_models.py")
def test_vocal_separation_runs(tmp_path):
    import soundfile as sf
    from anime.separate import separate_vocals
    t = np.arange(44100 * 2) / 44100
    sf.write(tmp_path / "a.wav", (0.2 * np.sin(2 * np.pi * 220 * t)).astype(np.float32), 44100)
    v, sr = separate_vocals(tmp_path / "a.wav")
    assert sr == 44100 and v.shape[0] == 2 and np.isfinite(v).all()
