"""High-level offline analysis, masking, batch and async APIs."""

from __future__ import annotations

import asyncio
import threading
import time
from html.parser import HTMLParser

from lpte.core.cache import LRUCache
from lpte.core.classifier import (
    SIGNAL_NAMES,
    ClassificationResult,
    Classifier,
    severity_for,
    validate_threshold,
)
from lpte.core.normalizer import TextNormalizer
from lpte.core.profile import LanguageProfile
from lpte.core.tokenizer import Tokenizer


class _TextParser(HTMLParser):
    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.parts: list[str] = []

    def handle_data(self, data: str) -> None:
        self.parts.append(data)

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        self.parts.append(" ")

    def handle_endtag(self, tag: str) -> None:
        self.parts.append(" ")


def _strip_html(html: str) -> str:
    """Extract visible text, decoding entities exactly once (not an HTML sanitizer)."""
    parser = _TextParser()
    parser.feed(html)
    parser.close()
    return "".join(parser.parts)


def _check_mask(mask: str) -> None:
    if not isinstance(mask, str) or len(mask) != 1 or mask.isspace():
        raise ValueError("mask must be a single non-whitespace character")


class LpteEngine:
    """Compile a language profile once; reuse the engine across requests.

    All caches are bounded and per-engine. Profile data must not be mutated
    after constructing an engine; reload the profile to pick up new rules.
    """

    def __init__(
        self,
        profile: LanguageProfile,
        default_threshold: float = 0.6,
        cache_size: int = 512,
    ) -> None:
        validate_threshold(default_threshold)
        if type(cache_size) is not int or cache_size < 0:
            raise ValueError("cache_size must be a non-negative integer")
        self.profile = profile
        self.default_threshold = default_threshold
        self.normalizer = TextNormalizer()
        self.classifier = Classifier(profile)
        self.tokenizer = Tokenizer(self.classifier.cjk_lengths)
        # Store threshold-free evidence. A result is always copied before it
        # leaves the engine, so users cannot corrupt later cached requests.
        self._cache: LRUCache[str, ClassificationResult] | None = (
            LRUCache(cache_size) if cache_size else None
        )
        self._stats_lock = threading.Lock()
        self._total_analyzed = 0
        self._total_toxic = 0
        self._total_time_ms = 0.0

    def analyze(self, text: str, threshold: float | None = None) -> ClassificationResult:
        if not isinstance(text, str):
            raise TypeError("text must be a string")
        threshold = self.default_threshold if threshold is None else threshold
        validate_threshold(threshold)
        start = time.perf_counter()
        evidence = self._cache.get(text) if self._cache is not None else None
        if evidence is None:
            evidence = self._analyze_uncached(text)
            if self._cache is not None:
                self._cache.put(text, evidence)
        result = evidence.at_threshold(threshold)
        with self._stats_lock:
            self._total_analyzed += 1
            self._total_toxic += int(result.is_toxic)
            self._total_time_ms += (time.perf_counter() - start) * 1000
        return result

    def is_toxic(self, text: str, threshold: float | None = None) -> bool:
        return self.analyze(text, threshold).is_toxic

    def sanitize(self, text: str, mask: str = "*", threshold: float | None = None) -> str:
        """Mask original, not normalized, surfaces for every detected term."""
        _check_mask(mask)
        result = self.analyze(text, threshold)
        if not result.is_toxic:
            return text
        variants = self.normalizer.normalize_variants_with_spans(text)
        covered = [False] * len(text)
        for match in result.matches:
            variant = variants[match.variant]
            start, end = variant.original_span(match.start, match.end)
            covered[start:end] = [True] * (end - start)
        return "".join(mask if covered[i] else c for i, c in enumerate(text))

    def batch_analyze(
        self,
        texts: list[str],
        threshold: float | None = None,
    ) -> list[ClassificationResult]:
        return [self.analyze(t, threshold) for t in texts]

    async def analyze_async(
        self, text: str, threshold: float | None = None
    ) -> ClassificationResult:
        """Execute CPU work in a thread instead of blocking an asyncio loop."""
        return await asyncio.to_thread(self.analyze, text, threshold)

    async def batch_analyze_async(
        self,
        texts: list[str],
        threshold: float | None = None,
    ) -> list[ClassificationResult]:
        return await asyncio.to_thread(self.batch_analyze, texts, threshold)

    def analyze_html(self, html: str, threshold: float | None = None) -> ClassificationResult:
        return self.analyze(_strip_html(html), threshold)

    def cache_stats(self) -> dict[str, object] | None:
        return self._cache.stats() if self._cache is not None else None

    def engine_stats(self) -> dict[str, object]:
        with self._stats_lock:
            count, toxic, elapsed = self._total_analyzed, self._total_toxic, self._total_time_ms
        return {
            "total_analyzed": count,
            "total_toxic": toxic,
            "detection_rate": toxic / count if count else 0.0,
            "avg_latency_ms": round(elapsed / count, 3) if count else 0.0,
            "language_code": self.profile.language_code,
            "language_name": self.profile.language_name,
            "vocabulary_size": len(self.profile.bad_words),
            "cache": self.cache_stats(),
        }

    def clear_cache(self) -> None:
        if self._cache is not None:
            self._cache.clear()

    def _analyze_uncached(self, text: str) -> ClassificationResult:
        variants = self.normalizer.normalize_with_alternatives(text)
        results = [
            self.classifier.classify(self.tokenizer.tokenize(v), self.profile) for v in variants
        ]
        confidence = max(r.confidence for r in results)
        matches = tuple(
            # Copy offsets with their normalization-variant id so sanitize()
            # can recover exactly the span that produced this match.
            type(m)(m.term, m.category, m.signal, m.start, m.end, i, m.language)
            for i, r in enumerate(results)
            for m in r.matches
        )
        terms = list(dict.fromkeys(m.term for m in matches))
        categories = list(dict.fromkeys(m.category for m in matches))
        signals = {name: max(r.signals[name] for r in results) for name in SIGNAL_NAMES}
        return ClassificationResult(
            bool(confidence and confidence >= self.default_threshold),
            severity_for(confidence, set(categories)),
            confidence,
            terms,
            signals,
            categories,
            self.profile.language_code if matches else "",
            matches,
        )
