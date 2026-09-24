"""
Context-rule correctness — the difference between a usable filter and a toy.

These tests lock in the fix for a false-negative class where a benign word
anywhere in the text suppressed a genuine match, plus the compound/idiom
behaviour that unspaced scripts depend on.
"""

import pytest

from lpte.core.engine import LpteEngine
from lpte.languages.bn import BengaliProfile
from lpte.languages.en import EnglishProfile
from lpte.languages.ja import JapaneseProfile


@pytest.fixture
def en():
    return LpteEngine(EnglishProfile, cache_size=0)


@pytest.fixture
def bn():
    return LpteEngine(BengaliProfile, cache_size=0)


@pytest.fixture
def ja():
    return LpteEngine(JapaneseProfile, cache_size=0)


class TestContextRulesDoNotOverSuppress:
    """A clean word elsewhere in the text must NOT mask a real violation."""

    def test_benign_word_elsewhere_does_not_mask_toxicity(self, en):
        # Regression: "passed" contains "ass" and used to suppress the
        # genuine "ass" later in the same message.
        assert en.analyze("I passed the exam. you ass!").is_toxic

    def test_benign_word_alone_still_clean(self, en):
        assert not en.analyze("I passed the exam").is_toxic

    def test_unrelated_clean_word_does_not_mask(self, en):
        assert en.analyze("hello there, you bitch").is_toxic

    def test_compound_in_one_place_does_not_mask_another(self, en):
        # "classroom" is clean; "ass" on its own is not.
        assert en.analyze("the classroom is nice but you are an ass").is_toxic


class TestBenignCollocationsAllowed:
    """Everyday usage of nouns that double as insults must pass."""

    @pytest.mark.parametrize("text", [
        "please take out the trash",
        "the garbage truck is here",
        "please kill the background process",
        "there is a trash can outside",
    ])
    def test_english_benign_nouns(self, en, text):
        assert not en.analyze(text).is_toxic, text

    @pytest.mark.parametrize("text", [
        "you are trash",
        "what a garbage human being",
    ])
    def test_english_insults_still_flagged(self, en, text):
        assert en.analyze(text).is_toxic, text


class TestUnspacedScriptCompounds:
    """
    Japanese/Bengali have no spaces, so 'clean variant' checks must work on
    compounds: 豚 (insult) is clean inside 豚肉 (pork) but toxic standalone.
    """

    def test_pork_is_clean(self, ja):
        assert not ja.analyze("美味しい豚肉を食べました").is_toxic

    def test_trash_can_is_clean(self, ja):
        assert not ja.analyze("ゴミ箱を捨てた").is_toxic

    def test_bare_insult_is_toxic(self, ja):
        assert ja.analyze("豚が嫌い").is_toxic

    def test_bengali_idiom_is_clean(self, bn):
        assert not bn.analyze("পাগলের মতো হাসছে").is_toxic


class TestBengaliFalsePositiveRemovals:
    """
    Words that were wrongly listed as profanity and made the pack unusable
    for ordinary Bengali text.
    """

    @pytest.mark.parametrize("text", [
        "আমার মায়ের হাতের রান্না খুব ভালো",      # mother's cooking
        "আমি আমার বোনের সাথে বাজারে গিয়েছিলাম",   # went with my sister
        "গরুর দুধ খুব পুষ্টিকর",                   # cow's milk is nutritious
        "আমি দুধ খাই",                            # I drink milk
        "ফোনটা নষ্ট হয়ে গেছে",                    # the phone broke
        "খাবার নষ্ট হয়েছে",                       # the food spoiled
        "নোংরা পানি পরিষ্কার করো",                 # clean the dirty water
        "রুটি পোড়া হয়ে গেছে",                    # the bread is burnt
    ])
    def test_innocent_sentences_are_clean(self, bn, text):
        assert not bn.analyze(text).is_toxic, text


class TestReligiousIdentityFairness:
    """Identity words must never be treated as profanity."""

    @pytest.mark.parametrize("text", [
        "আমি মুসলিম",
        "সে হিন্দু",
        "হিন্দু ও মুসলিম একসাথে থাকে",
    ])
    def test_identity_terms_are_clean(self, bn, text):
        assert not bn.analyze(text).is_toxic, text


class TestBengaliDetectionStillWorks:
    """The false-positive fixes must not have gutted recall."""

    @pytest.mark.parametrize("text", [
        "কুত্তা",
        "কুত্তারা",
        "হারামজাদা",
        "মাদারচোদ",
        "চোদ",
        "তুই একটা গাধা",
        "সে একটা নষ্ট লোক",
    ])
    def test_real_profanity_still_detected(self, bn, text):
        assert bn.analyze(text).is_toxic, text


class TestSentenceFinalPunctuation:
    """Trailing '!' must not turn 'ass' into 'assi' and hide the match."""

    @pytest.mark.parametrize("text", [
        "What the hell!",
        "you are an idiot!",
        "shut up!",
    ])
    def test_exclamation_still_detected(self, en, text):
        assert en.analyze(text).is_toxic, text

    @pytest.mark.parametrize("text", [
        "Hey there!",
        "Great job!",
        "Congratulations!",
    ])
    def test_exclamation_on_clean_text_stays_clean(self, en, text):
        assert not en.analyze(text).is_toxic, text
