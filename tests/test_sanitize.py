"""
Sanitization tests.

Detection without masking is half a feature: if the engine flags "f4ck" but
sanitize() returns it untouched, the integrator still ships the abuse.
"""

import pytest

from lpte.core.engine import LpteEngine
from lpte.languages.bn import BengaliProfile
from lpte.languages.en import EnglishProfile


@pytest.fixture
def en():
    return LpteEngine(EnglishProfile, cache_size=0)


class TestPlainMasking:
    def test_masks_plain_profanity(self, en):
        assert en.sanitize("you are a bastard") == "you are a *******"

    def test_preserves_clean_text(self, en):
        text = "hello world, the weather is nice"
        assert en.sanitize(text) == text

    def test_mask_character_is_configurable(self, en):
        assert en.sanitize("you are a bastard", mask="#") == "you are a #######"

    def test_mask_length_matches_word(self, en):
        out = en.sanitize("bastard")
        assert out == "*" * len("bastard")

    def test_case_preserved_outside_the_word(self, en):
        assert en.sanitize("You Bastard") == "You *******"


class TestObfuscatedMasking:
    """The regression class: detected as toxic, but returned unmasked."""

    @pytest.mark.parametrize("text", [
        "f4ck",            # leetspeak
        "f@ck",            # symbol substitution
        "$hit",            # dollar for s
        "f.u.c.k",         # separator insertion
        "f u c k",         # word splitting
        "shiiit",          # repeated characters
        "FuCk",            # mixed case
        "f u c k off",     # split inside a sentence
    ])
    def test_obfuscation_is_masked(self, en, text):
        result = en.sanitize(text)
        assert not any(ch.isalpha() and ch not in "off" for ch in result) or "*" in result, text

    def test_leetspeak_fully_masked(self, en):
        assert en.sanitize("f4ck") == "****"

    def test_separator_insertion_masked(self, en):
        assert en.sanitize("f.u.c.k") == "*******"

    def test_repeated_chars_masked(self, en):
        assert en.sanitize("shiiit") == "******"

    def test_split_word_masked(self, en):
        assert en.sanitize("f u c k") == "* * * *"

    def test_obfuscation_in_sentence(self, en):
        out = en.sanitize("hey f4ck you")
        assert "f4ck" not in out
        assert "hey" in out and "you" in out


class TestSplitWordMaskingScope:
    """Masking a split profanity must not swallow neighbouring clean words."""

    def test_clean_words_preserved_around_split_profanity(self, en):
        out = en.sanitize("hey there f u c k off")
        assert "hey" in out and "there" in out

    def test_masks_only_the_matching_window(self, en):
        # "a b c d" contains no profanity — nothing may be masked.
        assert en.sanitize("a b c d e") == "a b c d e"


class TestMultiWordPhrases:
    def test_phrase_is_masked(self, en):
        out = en.sanitize("you should kill yourself now")
        assert "kill yourself" not in out.replace("*", "")

    def test_multilingual_masking(self):
        bn = LpteEngine(BengaliProfile, cache_size=0)
        out = bn.sanitize("তুই একটা কুত্তা")
        assert "কুত্তা" not in out


class TestSanitizeConsistency:
    """Whatever analysis flags must be what sanitize masks."""

    @pytest.mark.parametrize("text", [
        "you are a fucking idiot",
        "f4ck this bullsh1t",
        "shut up you worthless loser",
        "I will kill you",
    ])
    def test_flagged_text_is_actually_changed(self, en, text):
        assert en.analyze(text).is_toxic
        assert en.sanitize(text) != text

    @pytest.mark.parametrize("text", [
        "hello how are you",
        "please take out the trash",
        "kill the background process",
    ])
    def test_clean_text_is_unchanged(self, en, text):
        assert not en.analyze(text).is_toxic
        assert en.sanitize(text) == text
