"""
Moderation policy tests.

A boolean "is it toxic" is not a product decision. These tests verify that
the policy layer maps the same confidence to different actions depending on
what kind of harm was detected and who the audience is.
"""

import pytest

from lpte.core.engine import LpteEngine
from lpte.core.policy import (
    Action,
    ModerationPolicy,
    get_policy,
    policy_balanced,
    policy_lenient,
    policy_strict,
)
from lpte.languages.en import EnglishProfile


@pytest.fixture
def engine():
    return LpteEngine(EnglishProfile, cache_size=0)


def decide(engine, text, policy):
    return policy.decide(engine.analyze(text))


class TestPresets:
    def test_all_presets_available(self):
        assert get_policy("strict").block_above < get_policy("balanced").block_above
        assert get_policy("balanced").block_above <= get_policy("lenient").block_above

    def test_unknown_preset_raises(self):
        with pytest.raises(ValueError):
            get_policy("nonexistent")


class TestCleanContent:
    @pytest.mark.parametrize("name", ["strict", "balanced", "lenient"])
    def test_clean_text_always_allowed(self, engine, name):
        d = decide(engine, "hello, how are you today?", get_policy(name))
        assert d.action == Action.ALLOW
        assert d.should_publish
        assert not d.needs_review


class TestHarmDifferentiation:
    """
    The core requirement: identical confidence, different consequence.
    "damn" and a racial slur both score ~0.80 but must not be treated alike.
    """

    def test_swearing_is_masked_not_blocked_in_balanced(self, engine):
        d = decide(engine, "damn this is good", policy_balanced())
        assert d.action == Action.MASK

    def test_slur_is_blocked_in_balanced(self, engine):
        d = decide(engine, "you nigger", policy_balanced())
        assert d.action == Action.BLOCK

    def test_threat_is_blocked_in_every_preset(self, engine):
        for name in ("strict", "balanced", "lenient"):
            d = decide(engine, "I will kill you", get_policy(name))
            assert d.action == Action.BLOCK, name

    def test_slur_blocked_even_in_lenient(self, engine):
        # Adult/gaming contexts tolerate swearing, never identity attacks.
        d = decide(engine, "you nigger", policy_lenient())
        assert d.action == Action.BLOCK

    def test_swearing_tolerated_in_lenient(self, engine):
        assert decide(engine, "this is bullshit", policy_lenient()).action == Action.ALLOW

    def test_swearing_blocked_in_strict(self, engine):
        assert decide(engine, "this is bullshit", policy_strict()).action == Action.BLOCK


class TestWeightedGravity:
    def test_slur_weighs_more_than_profanity(self):
        policy = policy_balanced()
        assert policy.weighted_score(0.8, ["slur"]) > policy.weighted_score(0.8, ["profanity"])

    def test_weighted_score_is_capped_at_one(self):
        assert policy_balanced().weighted_score(1.0, ["slur"]) == 1.0

    def test_unknown_category_uses_default_weight(self):
        policy = policy_balanced()
        assert policy.weighted_score(0.5, ["something_else"]) < 0.5


class TestDenyAndAllowLists:
    def test_denylist_forces_block(self, engine):
        policy = policy_lenient()
        policy.denylist.add("damn")
        d = decide(engine, "damn this is good", policy)
        assert d.action == Action.BLOCK
        assert d.reason == "denylisted_term"

    def test_denylist_does_not_affect_other_text(self, engine):
        policy = policy_lenient()
        policy.denylist.add("damn")
        assert decide(engine, "hello world", policy).action == Action.ALLOW

    def test_allowlist_downgrades_to_flag(self, engine):
        policy = policy_strict()
        policy.allowlist.add("damn")
        d = decide(engine, "damn this is good", policy)
        assert d.action == Action.FLAG
        assert d.needs_review

    def test_allowlist_does_not_hide_slurs(self, engine):
        policy = policy_balanced()
        policy.allowlist.add("damn")
        # "damn" is allowlisted but a slur is present — must still block.
        assert decide(engine, "damn you nigger", policy).action == Action.BLOCK


class TestZeroToleranceCategories:
    def test_threat_is_zero_tolerance_by_default(self):
        assert "threat" in policy_balanced().always_block_categories

    def test_zero_tolerance_can_be_disabled(self, engine):
        policy = policy_balanced()
        policy.always_block_categories = set()
        d = decide(engine, "I will kill you", policy)
        # Falls through to the confidence-graded path.
        assert d.action in (Action.MASK, Action.BLOCK, Action.FLAG)


class TestDecisionPayload:
    def test_as_dict_is_json_serialisable(self, engine):
        import json
        d = decide(engine, "you are a fucking idiot", policy_balanced())
        payload = d.as_dict()
        json.dumps(payload)  # must not raise
        assert payload["action"] in ("ALLOW", "FLAG", "MASK", "BLOCK")
        assert isinstance(payload["should_publish"], bool)

    def test_categories_and_terms_reported(self, engine):
        d = decide(engine, "you are a fucking idiot", policy_balanced())
        assert "profanity" in d.categories
        assert d.matched_terms


class TestCustomPolicy:
    def test_custom_thresholds_respected(self, engine):
        policy = ModerationPolicy(
            category_thresholds={"profanity": 0.99},  # effectively ignore swearing
            default_threshold=0.6,
            mask_above=0.6,
            block_above=0.9,
        )
        assert decide(engine, "this is bullshit", policy).action == Action.ALLOW
