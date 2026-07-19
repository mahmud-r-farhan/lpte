"""Tests for Classifier."""

import pytest

from lpte.core.classifier import Classifier, Severity
from lpte.core.tokenizer import Tokenizer
from lpte.languages.en import EnglishProfile


@pytest.fixture
def clf():
    return Classifier()


@pytest.fixture
def tok():
    return Tokenizer()


@pytest.fixture
def profile():
    return EnglishProfile


class TestExactMatching:
    def test_detects_exact_profanity(self, clf, tok, profile):
        tokens = tok.tokenize("fuck")
        result = clf.classify(tokens, profile)
        assert result.is_toxic
        assert "fuck" in result.matched_terms

    def test_detects_multiple_profanity(self, clf, tok, profile):
        tokens = tok.tokenize("fuck shit")
        result = clf.classify(tokens, profile)
        assert result.is_toxic
        assert len(result.matched_terms) >= 2


class TestFalsePositives:
    def test_clean_words_not_flagged(self, clf, tok, profile):
        tokens = tok.tokenize("hello world")
        result = clf.classify(tokens, profile)
        assert not result.is_toxic
        assert result.severity == Severity.NONE

    def test_class_not_flagged(self, clf, tok, profile):
        tokens = tok.tokenize("class")
        result = clf.classify(tokens, profile, threshold=0.5)
        assert "ass" not in result.matched_terms

    def test_grass_not_flagged(self, clf, tok, profile):
        tokens = tok.tokenize("grass")
        result = clf.classify(tokens, profile)
        assert "ass" not in result.matched_terms

    def test_bass_not_flagged(self, clf, tok, profile):
        tokens = tok.tokenize("bass")
        result = clf.classify(tokens, profile)
        assert "ass" not in result.matched_terms


class TestSeverityLevels:
    def test_critical_for_confident_matches(self, clf, tok, profile):
        tokens = tok.tokenize("motherfucker")
        result = clf.classify(tokens, profile)
        assert result.severity >= Severity.HIGH

    def test_none_for_clean_text(self, clf, tok, profile):
        tokens = tok.tokenize("the weather is nice today")
        result = clf.classify(tokens, profile)
        assert result.severity == Severity.NONE
