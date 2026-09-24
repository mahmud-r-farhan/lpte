"""
Performance regression tests.

These budgets are deliberately loose (they must pass on slow CI boxes and
under load) — they exist to catch an order-of-magnitude regression, such as
someone reintroducing an O(vocabulary) scan per token, not to measure
absolute speed. Use `lpte bench` for real numbers.
"""

import statistics
import time

import pytest

from lpte.core.engine import LpteEngine
from lpte.languages.bn import BengaliProfile
from lpte.languages.en import EnglishProfile

# Generous per-call budgets in milliseconds (warm, no cache).
SHORT_BUDGET_MS = 1.0     # one chat line
MEDIUM_BUDGET_MS = 2.0    # a paragraph
LONG_BUDGET_MS = 15.0     # 120-word comment — was ~28ms before optimisation

SHORT_TEXTS = [
    "hello how are you",
    "see you tomorrow",
    "thanks for the update",
    "good morning everyone",
]

MEDIUM_TEXTS = [
    "hey everyone, the deployment finished and all tests are green, great work team",
    "can someone review my pull request when they get a chance, thanks in advance",
    "the meeting is moved to tomorrow morning, please update your calendars",
]

LONG_TEXT = " ".join("word%d" % i for i in range(120))


@pytest.fixture(scope="module")
def en():
    engine = LpteEngine(EnglishProfile, cache_size=0)
    # Warm up module-level caches (stem memo, regex JIT, etc.)
    for t in SHORT_TEXTS + MEDIUM_TEXTS + [LONG_TEXT]:
        engine.analyze(t)
    return engine


def _measure(engine, text, repeats=30):
    times = []
    for _ in range(repeats):
        t0 = time.perf_counter()
        engine.analyze(text)
        times.append((time.perf_counter() - t0) * 1000)
    return statistics.median(times)


class TestLatencyBudgets:
    @pytest.mark.parametrize("text", SHORT_TEXTS)
    def test_short_messages(self, en, text):
        assert _measure(en, text) < SHORT_BUDGET_MS, text

    @pytest.mark.parametrize("text", MEDIUM_TEXTS)
    def test_medium_messages(self, en, text):
        assert _measure(en, text) < MEDIUM_BUDGET_MS, text

    def test_long_comment(self, en):
        # The worst case before optimisation: clean long text still pays for
        # every analysis stage, including the fuzzy pass.
        assert _measure(en, LONG_TEXT, repeats=10) < LONG_BUDGET_MS


class TestThroughput:
    def test_batch_throughput(self, en):
        """Batch analysis must stay sub-millisecond per short message."""
        texts = ["hello world, how are you today"] * 300
        t0 = time.perf_counter()
        en.batch_analyze(texts)
        elapsed_ms = (time.perf_counter() - t0) * 1000
        per_text = elapsed_ms / len(texts)
        assert per_text < SHORT_BUDGET_MS, f"{per_text:.3f} ms/text"


class TestScaling:
    """
    Cost must grow roughly linearly with input length, not quadratically.
    A 4x longer message should cost well under 16x the time.
    """

    def test_linear_scaling(self, en):
        short = " ".join("word%d" % i for i in range(30))
        long_ = " ".join("word%d" % i for i in range(120))
        en.analyze(short)
        en.analyze(long_)
        t_short = _measure(en, short, repeats=15)
        t_long = _measure(en, long_, repeats=15)
        ratio = t_long / max(t_short, 1e-6)
        assert ratio < 16.0, f"4x length cost {ratio:.1f}x time"


class TestCacheEffectiveness:
    def test_cache_eliminates_repeat_work(self):
        engine = LpteEngine(EnglishProfile, cache_size=64)
        text = "you are a fucking idiot"
        engine.analyze(text)
        engine.analyze(text)
        stats = engine.cache_stats()
        assert stats["hits"] >= 1
        assert stats["size"] >= 1

    def test_cache_key_is_threshold_independent(self):
        """
        The same text analysed at different thresholds must reuse one entry:
        confidence/severity/categories do not depend on the threshold.
        """
        engine = LpteEngine(EnglishProfile, cache_size=64)
        engine.analyze("you are a fucking idiot", 0.6)
        engine.analyze("you are a fucking idiot", 0.9)
        assert engine.cache_stats()["hits"] >= 1

    def test_threshold_override_still_correct(self):
        engine = LpteEngine(EnglishProfile, cache_size=64)
        lenient = engine.analyze("damn", 0.3)
        strict = engine.analyze("damn", 0.99)
        if lenient.confidence > 0:
            assert lenient.is_toxic is True
            assert strict.is_toxic is False


class TestBengaliPerformance:
    def test_bengali_within_budget(self):
        engine = LpteEngine(BengaliProfile, cache_size=0)
        text = "আমি বাংলায় কথা বলি এবং আজ আবহাওয়া খুব ভালো " * 8
        engine.analyze(text)
        assert _measure(engine, text, repeats=10) < LONG_BUDGET_MS
