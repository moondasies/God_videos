import json

import numpy as np

from animation.characters import GIRL_IDENTITY, MAHADEV_IDENTITY, WARDROBE
from animation.rig import EXPRESSIONS, VISEMES, expr_params, ik, viseme_params
from animation.scene import EpisodeRenderer
from pipeline.qa import IDENTITY_LOCK, current_identity_hashes


def test_expression_blend_and_visemes():
    p = expr_params({"smile": 0.5, "sad": 0.5})
    assert -0.1 < p["smile"] < 0.3
    assert set(VISEMES) == set("ABCDEFGHX")
    assert viseme_params("D")["open"] > viseme_params("B")["open"] > viseme_params("A")["open"]
    assert "peaceful" in EXPRESSIONS


def test_ik_reaches_target_within_range():
    E, W = ik((0, 0), (100, 100), 100, 100, outward=-1)
    assert np.hypot(W[0] - 100, W[1] - 100) < 1.0


def test_identity_locked():
    assert json.loads(IDENTITY_LOCK.read_text()) == current_identity_hashes()
    assert GIRL_IDENTITY["hair"] and MAHADEV_IDENTITY["moon"]


def _tl(shot):
    base = dict(id="x", start=0.0, duration=2.0, lines=[], background="bedroom_night", framing="two_shot", type="dialogue")
    base.update(shot)
    return {"shots": [base], "characters": {"girl": {"outfit": "home_tshirt"}},
            "moral": {"roman": "Test moral.", "english": "Test."}}


def test_frames_render_and_move():
    R = EpisodeRenderer(_tl({}), 135, 240)
    a, b = R.render(0, 0.2).astype(float), R.render(0, 1.4).astype(float)
    assert a.shape == (240, 135, 4)
    assert a[..., :3].std() > 10            # not a blank frame
    assert np.abs(a - b).mean() > 0.05      # something animates (blink/breath/sway/camera)


def test_every_background_and_outfit_renders():
    from animation.backgrounds import BACKGROUNDS
    for bg in BACKGROUNDS:
        R = EpisodeRenderer(_tl({"background": bg}), 90, 160)
        assert R.render(0, 0.5)[..., :3].std() > 3, bg
    for o in WARDROBE:
        R = EpisodeRenderer(_tl({"actors": {"girl": {"outfit": o}}}), 90, 160)
        R.render(0, 0.5)
