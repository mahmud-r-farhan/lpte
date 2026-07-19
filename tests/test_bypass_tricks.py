"""Comprehensive bypass-trick tests.

Tests that the engine catches intentional obfuscation patterns:
1. Leetspeak: f4ck, sh1t, @ss
2. Character insertion: f.u.c.k, f_u_c_k
3. Repeated characters: fuuuck, shiiit
4. Zero-width characters: f\u200Bu\u200Bck
5. Word splitting: "f u c k"
6. Mixed case: FuCk, fUcK
"""

import pytest

from lpte.core.engine import LpteEngine
from lpte.languages.en import EnglishProfile


@pytest.fixture
def engine():
    return LpteEngine(EnglishProfile)


class TestLeetspeakBypass:
    def test_catches_4_for_a(self, engine):
        assert engine.is_toxic("f4ck")

    def test_catches_1_for_i(self, engine):
        assert engine.is_toxic("sh1t")

    def test_catches_at_for_a(self, engine):
        assert engine.is_toxic("@ss")

    def test_catches_dollar_for_s(self, engine):
        assert engine.is_toxic("$hit")

    def test_catches_combined_leet(self, engine):
        assert engine.is_toxic("f@ck1ng")


class TestCharacterInsertion:
    def test_catches_dot_separators(self, engine):
        assert engine.is_toxic("f.u.c.k")

    def test_catches_underscore_separators(self, engine):
        assert engine.is_toxic("f_u_c_k")

    def test_catches_dash_separators(self, engine):
        assert engine.is_toxic("f-u-c-k")


class TestWordSplitting:
    def test_catches_split_via_concat(self, engine):
        result = engine.analyze("f u c k")
        assert result.signals["concat_match"] > 0 or result.is_toxic


class TestRepeatedCharacters:
    def test_catches_with_repeated_vowels(self, engine):
        assert engine.is_toxic("shiiit")

    def test_catches_with_repeated_consonants(self, engine):
        assert engine.is_toxic("buullshit")


class TestZeroWidthBypass:
    def test_catches_zero_width_space(self, engine):
        assert engine.is_toxic("f\u200Bu\u200Bc\u200Bk")

    def test_catches_zero_width_joiner(self, engine):
        assert engine.is_toxic("f\u200Duck")

    def test_catches_soft_hyphen(self, engine):
        assert engine.is_toxic("f\u00ADuck")


class TestMixedCase:
    def test_catches_mixed_case(self, engine):
        assert engine.is_toxic("FuCk")
        assert engine.is_toxic("FUCK")
        assert engine.is_toxic("fUcK")


class TestCleanTextShouldPass:
    def test_clean_sentence_passes(self, engine):
        assert not engine.is_toxic("hello how are you today")

    def test_technical_terms_pass(self, engine):
        assert not engine.is_toxic("the class assessment was great")

    def test_bengali_text_no_false_positive(self, engine):
        assert not engine.is_toxic("আমি বাংলায় কথা বলি")
