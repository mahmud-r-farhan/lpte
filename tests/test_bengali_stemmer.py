"""Tests for Bengali stemmer."""

import pytest

from lpte.languages.bn import BengaliStemmer


@pytest.fixture
def stemmer():
    return BengaliStemmer()


class TestCaseMarkerStripping:
    def test_strips_possessive_case(self, stemmer):
        result = stemmer.stem("কুত্তাটাকে")
        assert result.startswith("কুত্তা")

    def test_strips_case_marker_r(self, stemmer):
        assert stemmer.stem("কুত্তার") == "কুত্তা"

    def test_strips_case_marker_ke(self, stemmer):
        assert stemmer.stem("কুত্তাকে") == "কুত্তা"


class TestPluralStripping:
    def test_strips_plural_ra(self, stemmer):
        assert stemmer.stem("কুত্তারা") == "কুত্তা"


class TestDiminutiveStripping:
    def test_strips_diminutive_ta(self, stemmer):
        assert stemmer.stem("কুত্তাটা") == "কুত্তা"

    def test_strips_diminutive_ti(self, stemmer):
        assert stemmer.stem("কুত্তাটি") == "কুত্তা"


class TestShortWords:
    def test_short_words_returned_as_is(self, stemmer):
        assert stemmer.stem("বি") == "বি"
        assert stemmer.stem("আ") == "আ"


class TestUnknownWords:
    def test_unknown_words_returned_as_is(self, stemmer):
        assert stemmer.stem("বাংলাদেশ") == "বাংলাদেশ"
