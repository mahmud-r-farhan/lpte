"""Tests for Tokenizer."""

import pytest

from lpte.core.tokenizer import Tokenizer


@pytest.fixture
def tok():
    return Tokenizer()


class TestWordSplitting:
    def test_splits_on_whitespace(self, tok):
        result = tok.tokenize("hello world")
        assert result.words == ["hello", "world"]

    def test_handles_multiple_spaces(self, tok):
        result = tok.tokenize("hello   world")
        assert result.words == ["hello", "world"]

    def test_single_word(self, tok):
        result = tok.tokenize("hello")
        assert result.words == ["hello"]


class TestNgramGeneration:
    def test_generates_bigrams(self, tok):
        result = tok.tokenize("a b c d")
        assert result.bigrams == ["a b", "b c", "c d"]

    def test_generates_trigrams(self, tok):
        result = tok.tokenize("a b c d")
        assert result.trigrams == ["a b c", "b c d"]

    def test_empty_when_fewer_words(self, tok):
        result = tok.tokenize("hello")
        assert result.bigrams == []
        assert result.trigrams == []


class TestCharacterNgrams:
    def test_generates_char_bigrams(self, tok):
        grams = tok.character_ngrams("test", 2, 2)
        assert grams == ["te", "es", "st"]

    def test_generates_mixed_ngrams(self, tok):
        grams = tok.character_ngrams("test", 2, 3)
        assert "te" in grams
        assert "tes" in grams
