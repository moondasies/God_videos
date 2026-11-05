import pytest

from animation.draw import font, text_width
from animation.scene import CAPTION_MAX_W, caption_chunks
from pipeline.episode import EpisodeError, load_episode, validate_episode
from pipeline.scriptgen import TEMPLATES, build_episode_dict, match_pillar


@pytest.mark.parametrize("ep", ["episode_001", "episode_002"])
def test_sample_episodes_valid(ep):
    e = load_episode(ep)
    for s in e["shots"]:
        for ln in s.get("lines", []):
            assert ln["attribution"] == "original_fiction"
            assert any("ऀ" <= ch <= "ॿ" for ch in ln["tts"]), "TTS text must be Devanagari"


def test_invalid_outfit_rejected():
    e = load_episode("episode_001")
    e["characters"]["girl"]["outfit"] = "spacesuit"
    with pytest.raises(EpisodeError):
        validate_episode(e)


def test_topic_matching():
    assert match_pillar("Overthinking about my future") == "overthinking"
    assert match_pillar("my parents want me to get married") == "family_expectations"
    assert match_pillar("got another job rejection") == "career_failure"


@pytest.mark.parametrize("pillar", sorted(TEMPLATES))
def test_every_template_builds_valid_episode_with_fitting_captions(pillar):
    ep = build_episode_dict("t", TEMPLATES[pillar], "episode_test", 99)
    validate_episode(ep)
    f = font("Poppins-Bold", 56)
    for s in ep["shots"]:
        for ln in s["lines"]:
            ln = dict(ln, t0=0.0, t1=3.0)
            for _, _, words in caption_chunks(ln):
                assert text_width(" ".join(words), f) <= CAPTION_MAX_W, words
            assert len(ln["roman"]) <= 70
