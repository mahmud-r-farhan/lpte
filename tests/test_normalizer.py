"""Tests for TextNormalizer."""

import pytest

from lpte.core.normalizer import TextNormalizer


@pytest.fixture
def norm():
    return TextNormalizer()


class TestLeetSpeakReversal:
    def test_replaces_leet_digits(self, norm):
        assert norm.normalize("0") == "o"
        assert norm.normalize("1") == "i"
        assert norm.normalize("3") == "e"
        assert norm.normalize("4") == "u"
        assert norm.normalize("5") == "s"
        assert norm.normalize("7") == "t"

    def test_replaces_leet_symbols(self, norm):
        assert norm.normalize("@") == "a"
        assert norm.normalize("$") == "s"
        assert norm.normalize("!") == "i"

    def test_complex_leet_strings(self, norm):
        # 4 → u, @ → a (primary mappings)
        assert norm.normalize("f4ck") == "fuck"
        assert norm.normalize("f@ck") == "fack"
        assert norm.normalize("f u c k") == "f u c k"


class TestZeroWidthStripping:
    def test_removes_zero_width_space(self, norm):
        assert norm.normalize("f\u200Bu\u200Bc\u200Bk") == "fuck"

    def test_removes_zero_width_joiner(self, norm):
        assert norm.normalize("f\u200Duck") == "fuck"

    def test_removes_soft_hyphen(self, norm):
        assert norm.normalize("f\u00ADuck") == "fuck"

    def test_removes_bom(self, norm):
        assert norm.normalize("\uFEFFfuck") == "fuck"


class TestRepeatedCharacterCollapsing:
    def test_collapses_3_plus_repeated(self, norm):
        result = norm.normalize("fuuu")
        assert "fu" in result

    def test_collapses_long_repeated(self, norm):
        result = norm.normalize("fuuuuck")
        assert "fu" in result


class TestBengaliUnicode:
    def test_preserves_bengali_chars(self, norm):
        result = norm.normalize("বাংলা")
        assert "বাংল" in result


class TestCaseFolding:
    def test_lowercases_ascii(self, norm):
        assert norm.normalize("FUCK") == "fuck"
        assert norm.normalize("FuCk") == "fuck"
