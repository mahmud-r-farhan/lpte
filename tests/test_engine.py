"""End-to-end integration tests for LpteEngine."""

import time

import pytest

from lpte.core.engine import LpteEngine
from lpte.core.classifier import Severity
from lpte.languages.en import EnglishProfile
from lpte.languages.bn import BengaliProfile


class TestEnglishAnalysis:
    @pytest.fixture
    def engine(self):
        return LpteEngine(EnglishProfile)

    def test_detects_profanity_in_sentence(self, engine):
        result = engine.analyze("you are a fucking idiot")
        assert result.is_toxic
        assert len(result.matched_terms) > 0

    def test_returns_clean_for_normal_text(self, engine):
        result = engine.analyze("the weather is nice today")
        assert not result.is_toxic
        assert result.severity == Severity.NONE

    def test_sanitize_masks_toxic_words(self, engine):
        sanitized = engine.sanitize("you are a bastard")
        assert "bastard" not in sanitized

    def test_sanitize_preserves_clean_text(self, engine):
        text = "hello world"
        assert engine.sanitize(text) == text

    def test_handles_empty_input(self, engine):
        result = engine.analyze("")
        assert not result.is_toxic

    def test_handles_whitespace_only(self, engine):
        result = engine.analyze("   ")
        assert not result.is_toxic


class TestBengaliAnalysis:
    @pytest.fixture
    def engine(self):
        return LpteEngine(BengaliProfile)

    def test_detects_bengali_profanity(self, engine):
        result = engine.analyze("কুত্তা")
        assert result.is_toxic, "Should detect 'কুত্তা' as toxic"

    def test_detects_bengali_with_suffix(self, engine):
        result = engine.analyze("কুত্তারা")
        assert result.is_toxic, "Should detect inflected 'কুত্তারা' as toxic"

    def test_returns_clean_for_bengali_normal_text(self, engine):
        result = engine.analyze("আমি বাংলায় কথা বলি")
        assert not result.is_toxic, "Normal Bengali text should be clean"


class TestPerformanceBudget:
    def test_analysis_completes_under_25ms(self):
        engine = LpteEngine(EnglishProfile)
        texts = [
            "the quick brown fox jumps over the lazy dog",
            "this is a moderately long sentence with some words",
            "short",
            "a]sdfjkl; qwertyuiop asdfghjkl",
        ]

        for text in texts:
            start = time.perf_counter()
            engine.analyze(text)
            elapsed_ms = (time.perf_counter() - start) * 1000
            assert elapsed_ms < 25, f"Analysis of '{text}' took {elapsed_ms:.1f}ms (budget: 25ms)"
