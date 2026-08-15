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

    def test_result_has_signals_dict(self, engine):
        result = engine.analyze("you are a bastard")
        assert isinstance(result.signals, dict)
        assert "exact_match" in result.signals
        assert "phrase_match" in result.signals

    def test_confidence_between_0_and_1(self, engine):
        result = engine.analyze("some text")
        assert 0.0 <= result.confidence <= 1.0


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


class TestBatchAnalyze:
    @pytest.fixture
    def engine(self):
        return LpteEngine(EnglishProfile)

    def test_batch_returns_correct_length(self, engine):
        texts = ["hello world", "you fucking idiot", "nice day"]
        results = engine.batch_analyze(texts)
        assert len(results) == 3

    def test_batch_detects_toxic_in_list(self, engine):
        texts = ["clean text", "fucking hell", "another clean"]
        results = engine.batch_analyze(texts)
        assert results[0].is_toxic is False
        assert results[1].is_toxic is True
        assert results[2].is_toxic is False

    def test_batch_empty_list(self, engine):
        assert engine.batch_analyze([]) == []

    def test_batch_threshold_override(self, engine):
        # Very low threshold — almost everything should pass
        results = engine.batch_analyze(["hello"], threshold=0.01)
        assert len(results) == 1


class TestAnalyzeHtml:
    @pytest.fixture
    def engine(self):
        return LpteEngine(EnglishProfile)

    def test_strips_html_tags(self, engine):
        result = engine.analyze_html("<b>you are a</b> <i>bastard</i>")
        assert result.is_toxic

    def test_clean_html_passes(self, engine):
        result = engine.analyze_html("<p>Hello, <strong>world</strong>!</p>")
        assert not result.is_toxic

    def test_strips_html_entities(self, engine):
        result = engine.analyze_html("&lt;b&gt;hello&lt;/b&gt;")
        assert not result.is_toxic


class TestCaching:
    def test_cache_returns_same_result(self):
        engine = LpteEngine(EnglishProfile, cache_size=64)
        text = "you are a bastard"
        r1 = engine.analyze(text)
        r2 = engine.analyze(text)
        assert r1.is_toxic == r2.is_toxic
        assert r1.confidence == r2.confidence

    def test_cache_hit_increments_hits(self):
        engine = LpteEngine(EnglishProfile, cache_size=64)
        engine.analyze("hello world")
        engine.analyze("hello world")  # second call = cache hit
        stats = engine.cache_stats()
        assert stats["hits"] >= 1

    def test_cache_disabled_with_size_0(self):
        engine = LpteEngine(EnglishProfile, cache_size=0)
        assert engine.cache_stats() is None

    def test_clear_cache_empties_entries(self):
        engine = LpteEngine(EnglishProfile, cache_size=64)
        engine.analyze("hello world")
        engine.clear_cache()
        assert engine.cache_stats()["size"] == 0


class TestEngineStats:
    def test_stats_increment_on_analyze(self):
        engine = LpteEngine(EnglishProfile)
        engine.analyze("hello")
        engine.analyze("world")
        s = engine.engine_stats()
        assert s["total_analyzed"] == 2

    def test_stats_toxic_count(self):
        engine = LpteEngine(EnglishProfile)
        engine.analyze("clean text")
        engine.analyze("you fucking idiot")
        s = engine.engine_stats()
        assert s["total_toxic"] == 1

    def test_stats_contains_language_info(self):
        engine = LpteEngine(EnglishProfile)
        s = engine.engine_stats()
        assert s["language_code"] == "en"
        assert s["vocabulary_size"] > 0


class TestPerformanceBudget:
    def test_analysis_completes_under_25ms_english(self):
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

    def test_analysis_completes_under_25ms_bengali(self):
        engine = LpteEngine(BengaliProfile)
        texts = [
            "আমি বাংলায় কথা বলি",
            "কুত্তা",
            "হারামি কুত্তা",
        ]
        for text in texts:
            start = time.perf_counter()
            engine.analyze(text)
            elapsed_ms = (time.perf_counter() - start) * 1000
            assert elapsed_ms < 25, f"Bengali analysis of '{text}' took {elapsed_ms:.1f}ms (budget: 25ms)"

    def test_batch_of_10_under_100ms(self):
        engine = LpteEngine(EnglishProfile)
        texts = ["hello world " + str(i) for i in range(10)]
        start = time.perf_counter()
        engine.batch_analyze(texts)
        elapsed_ms = (time.perf_counter() - start) * 1000
        assert elapsed_ms < 100, f"Batch of 10 took {elapsed_ms:.1f}ms"
