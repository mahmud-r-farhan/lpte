"""Tests for English stemmer."""

import pytest

from lpte.languages.en import EnglishStemmer


@pytest.fixture
def stemmer():
    return EnglishStemmer()


class TestPluralStripping:
    def test_strips_s(self, stemmer):
        assert stemmer.stem("fucks") == "fuck"

    def test_strips_ies_and_restores_y(self, stemmer):
        assert stemmer.stem("cities") == "city"


class TestPastTense:
    def test_strips_ed(self, stemmer):
        assert stemmer.stem("fucked") == "fuck"

    def test_strips_ied_and_restores_y(self, stemmer):
        assert stemmer.stem("carried") == "carry"


class TestProgressive:
    def test_strips_ing(self, stemmer):
        assert stemmer.stem("fucking") == "fuck"


class TestAdjectiveSuffixes:
    def test_strips_ful(self, stemmer):
        assert stemmer.stem("harmful") == "harm"

    def test_strips_less(self, stemmer):
        assert stemmer.stem("hopeless") == "hope"

    def test_strips_ly(self, stemmer):
        assert stemmer.stem("slowly") == "slow"


class TestShortWords:
    def test_short_words_returned_as_is(self, stemmer):
        assert stemmer.stem("as") == "as"
        assert stemmer.stem("i") == "i"
