"""Moderation decisions should not be confused with detection confidence."""

import pytest

from lpte import Action, LpteEngine, ModerationPolicy, get_policy
from lpte.languages import EnglishProfile


@pytest.fixture(scope="module")
def engine():
    return LpteEngine(EnglishProfile, cache_size=0)


@pytest.mark.parametrize("message,category,severity,balanced,lenient", [
    ("damn this is good", "profanity", "HIGH", Action.MASK, Action.ALLOW),
    ("you are so stupid and ugly", "insult", "HIGH", Action.MASK, Action.FLAG),
    ("you nigger", "slur", "CRITICAL", Action.BLOCK, Action.BLOCK),
    ("I will kill you", "threat", "CRITICAL", Action.BLOCK, Action.BLOCK),
    ("please kill the background process", None, "NONE", Action.ALLOW, Action.ALLOW),
])
def test_harm_weighted_presets(engine, message, category, severity, balanced, lenient):
    result = engine.analyze(message)
    assert result.severity.name == severity
    assert category in result.categories if category else not result.categories
    assert get_policy("balanced").decide(result, message).action == balanced
    assert get_policy("lenient").decide(result, message).action == lenient


def test_slur_wins_when_mild_word_also_matched(engine):
    result = engine.analyze("damn you nigger")
    assert set(result.categories) == {"slur", "profanity"}
    for name in ("strict", "balanced", "lenient"):
        assert get_policy(name).decide(result).action == Action.BLOCK


def test_category_policy_ignores_global_binary_threshold(engine):
    result = engine.analyze("you nigger", threshold=.99)
    assert not result.is_toxic
    assert get_policy("balanced").decide(result).action == Action.BLOCK


def test_allowlist_filters_only_its_term_then_rescores(engine):
    result = engine.analyze("damn idiot")
    policy = ModerationPolicy(allowlist={"damn"}, block_above=.9)
    decision = policy.decide(result)
    assert decision.action == Action.MASK
    assert decision.matched_terms == ("idiot",)
    assert decision.confidence == .8
    policy.allowlist.add("idiot")
    assert policy.decide(result).action == Action.ALLOW


def test_allowlist_cannot_suppress_another_occurrence(engine):
    policy = ModerationPolicy(allowlist={"damn"})
    result = engine.analyze("damn you nigger")
    assert policy.decide(result).action == Action.BLOCK


def test_denylist_not_in_vocabulary_requires_original_text(engine):
    policy = ModerationPolicy(denylist={"our-brand-slur"})
    result = engine.analyze("our-brand-slur is banned")
    assert not result.is_toxic
    assert policy.decide(result).action == Action.ALLOW
    assert policy.decide(result, "our-brand-slur is banned").action == Action.BLOCK
    assert policy.decide(result, "our-brand-slurring is banned").action == Action.ALLOW


def test_presets_are_fresh_and_settings_validated():
    p = get_policy("balanced")
    p.allowlist.add("nigger")
    assert not get_policy("balanced").allowlist
    with pytest.raises(ValueError):
        get_policy("missing")
    with pytest.raises(ValueError):
        ModerationPolicy(category_thresholds={"unknown": .5})
    with pytest.raises(ValueError):
        ModerationPolicy(mask_above=.9, block_above=.6)
    with pytest.raises(ValueError):
        ModerationPolicy(category_thresholds={"slur": float("nan")})


def test_policy_decision_serializes(engine):
    decision = get_policy("balanced").decide(engine.analyze("damn"))
    assert decision.as_dict()["action"] == "MASK"
    assert decision.as_dict()["categories"] == ["profanity"]
