"""
LpteEngine — high-level API for toxicity analysis.

This is the primary entry point for consuming the library.

Usage:
    from lpte import LpteEngine
    from lpte.languages import EnglishProfile

    engine = LpteEngine(EnglishProfile)
    result = engine.analyze("some text")
    if result.is_toxic:
        print(f"Toxic: {result.severity} ({result.confidence})")

Advanced:
    # With caching (default: enabled, 512 entries)
    engine = LpteEngine(EnglishProfile, cache_size=512)

    # Batch analysis
    results = engine.batch_analyze(["text one", "text two"])

    # HTML input
    clean_result = engine.analyze_html("<b>hello</b> f*ck")
"""

from __future__ import annotations

import re
import time

from lpte.core.cache import LRUCache
from lpte.core.classifier import ClassificationResult, Classifier, Severity
from lpte.core.normalizer import TextNormalizer
from lpte.core.profile import LanguageProfile
from lpte.core.tokenizer import Tokenizer

# Regex to strip HTML tags for analyze_html()
_HTML_TAG_RE = re.compile(r"<[^>]+>")
_HTML_ENTITY_RE = re.compile(r"&(?:#\d+|#x[0-9a-fA-F]+|[a-zA-Z]+);")
_HTML_ENTITIES: dict[str, str] = {
    "&amp;": "&", "&lt;": "<", "&gt;": ">",
    "&quot;": '"', "&apos;": "'", "&nbsp;": " ",
}


def _strip_html(html: str) -> str:
    """Strip HTML tags and decode common entities."""
    # Decode named entities first
    for entity, char in _HTML_ENTITIES.items():
        html = html.replace(entity, char)
    # Decode remaining entities
    html = _HTML_ENTITY_RE.sub(" ", html)
    # Strip tags
    return _HTML_TAG_RE.sub(" ", html)


class LpteEngine:
    """High-level toxicity analysis engine with caching and batch support."""

    def __init__(
        self,
        profile: LanguageProfile,
        default_threshold: float = 0.6,
        cache_size: int = 512,
    ):
        """
        Args:
            profile: Language profile (bad words, stemmer, context rules).
            default_threshold: Default confidence threshold for toxic classification.
                               Can be overridden per-call.
            cache_size: LRU cache capacity for analysis results.
                        Set to 0 to disable caching.
        """
        self.profile = profile
        self.default_threshold = default_threshold
        self.normalizer = TextNormalizer()
        self.tokenizer = Tokenizer()
        self.classifier = Classifier()

        # Optional LRU cache
        self._cache: LRUCache[tuple, ClassificationResult] | None = (
            LRUCache(capacity=cache_size) if cache_size > 0 else None
        )

        # Engine-level statistics
        self._total_analyzed: int = 0
        self._total_toxic: int = 0
        self._total_time_ms: float = 0.0

    # ─── Public API ───────────────────────────────────────────────────────────

    def analyze(self, text: str, threshold: float | None = None) -> ClassificationResult:
        """
        Analyze text for toxic content.
        Tries multiple normalization variants to catch obfuscation.

        Args:
            text: Raw input text to analyze.
            threshold: Confidence threshold [0.0, 1.0]. Defaults to engine default.

        Returns:
            ClassificationResult with is_toxic, severity, confidence, matched_terms, signals.
        """
        if threshold is None:
            threshold = self.default_threshold

        # Cache lookup
        cache_key = (text, self.profile.language_code, threshold)
        if self._cache is not None:
            cached = self._cache.get(cache_key)
            if cached is not None:
                return cached

        t0 = time.perf_counter()

        result = self._analyze_uncached(text, threshold)

        elapsed_ms = (time.perf_counter() - t0) * 1000
        self._total_analyzed += 1
        self._total_time_ms += elapsed_ms
        if result.is_toxic:
            self._total_toxic += 1

        if self._cache is not None:
            self._cache.put(cache_key, result)

        return result

    def is_toxic(self, text: str, threshold: float | None = None) -> bool:
        """Quick check: is the text toxic?"""
        return self.analyze(text, threshold).is_toxic

    def sanitize(self, text: str, mask: str = "*", threshold: float | None = None) -> str:
        """
        Sanitize text by replacing toxic segments with a mask character.

        Args:
            text: Raw input text.
            mask: Character to use for masking (default: '*').
            threshold: Confidence threshold override.

        Returns:
            Text with toxic words replaced by mask * len(word).
        """
        result = self.analyze(text, threshold)
        if not result.is_toxic:
            return text

        sanitized = text
        for term in result.matched_terms:
            # Match whole words, case-insensitive, including common leet variations
            pattern = re.compile(r"\b" + re.escape(term) + r"\b", re.IGNORECASE)
            sanitized = pattern.sub(lambda m: mask * len(m.group()), sanitized)

        return sanitized

    def batch_analyze(
        self,
        texts: list[str],
        threshold: float | None = None,
    ) -> list[ClassificationResult]:
        """
        Analyze multiple texts in one call.

        Args:
            texts: List of raw input strings.
            threshold: Confidence threshold override (applied to all texts).

        Returns:
            List of ClassificationResult, one per input text, in order.
        """
        return [self.analyze(text, threshold) for text in texts]

    def analyze_html(self, html: str, threshold: float | None = None) -> ClassificationResult:
        """
        Analyze HTML content for toxic text — strips tags before analysis.

        Args:
            html: Raw HTML string.
            threshold: Confidence threshold override.

        Returns:
            ClassificationResult based on the plain-text content.
        """
        plain_text = _strip_html(html)
        return self.analyze(plain_text, threshold)

    def cache_stats(self) -> dict[str, object] | None:
        """
        Return cache statistics, or None if caching is disabled.
        """
        if self._cache is None:
            return None
        return self._cache.stats()

    def engine_stats(self) -> dict[str, object]:
        """
        Return engine-level statistics.
        """
        avg_ms = (
            self._total_time_ms / self._total_analyzed
            if self._total_analyzed > 0 else 0.0
        )
        return {
            "total_analyzed": self._total_analyzed,
            "total_toxic": self._total_toxic,
            "detection_rate": (
                self._total_toxic / self._total_analyzed
                if self._total_analyzed > 0 else 0.0
            ),
            "avg_latency_ms": round(avg_ms, 3),
            "language_code": self.profile.language_code,
            "language_name": self.profile.language_name,
            "vocabulary_size": len(self.profile.bad_words),
            "cache": self._cache.stats() if self._cache else None,
        }

    def clear_cache(self) -> None:
        """Evict all cached results."""
        if self._cache is not None:
            self._cache.clear()

    # ─── Internal ─────────────────────────────────────────────────────────────

    def _analyze_uncached(self, text: str, threshold: float) -> ClassificationResult:
        """Core analysis logic — no caching layer."""
        # Try primary normalization first
        normalized = self.normalizer.normalize(text)
        tokens = self.tokenizer.tokenize(normalized)
        result = self.classifier.classify(tokens, self.profile, threshold)
        if result.is_toxic:
            return result

        # Try alternative normalizations (leet alternatives, aggressive collapse)
        variants = self.normalizer.normalize_with_alternatives(text)
        for variant in variants[1:]:  # skip primary (already tried)
            tokens = self.tokenizer.tokenize(variant)
            variant_result = self.classifier.classify(tokens, self.profile, threshold)
            if variant_result.is_toxic:
                return variant_result
            # Keep the best result if nothing is toxic
            if variant_result.confidence > result.confidence:
                result = variant_result

        return result
