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

    # Async (event-loop friendly, e.g. FastAPI handlers)
    result = await engine.analyze_async("some text")
"""

from __future__ import annotations

import asyncio
import html as _html
import re
import time
from dataclasses import replace

from lpte.core.cache import LRUCache
from lpte.core.classifier import ClassificationResult, Classifier, Severity, _edit_distance_1
from lpte.core.normalizer import TextNormalizer
from lpte.core.profile import LanguageProfile
from lpte.core.tokenizer import Tokenizer

# ─── Threshold Presets ────────────────────────────────────────────────────────
# Real-world moderation tiers:
#   STRICT   — kids' platforms, brand-safe contexts (more false positives OK)
#   BALANCED — general community default
#   LENIENT  — adult forums / gaming voice chat (only flag clear violations)
THRESHOLD_STRICT = 0.45
THRESHOLD_BALANCED = 0.6
THRESHOLD_LENIENT = 0.75

# Regex to strip HTML tags for analyze_html()
_HTML_TAG_RE = re.compile(r"<[^>]+>")

# Whitespace splitter that keeps separators (for sanitize token masking)
_WS_SPLIT_RE = re.compile(r"(\s+)")


def _strip_html(html: str) -> str:
    """Strip HTML tags and decode entities (single-pass, no double-decoding)."""
    return _HTML_TAG_RE.sub(" ", _html.unescape(html))


class LpteEngine:
    """High-level toxicity analysis engine with caching and batch support."""

    def __init__(
        self,
        profile: LanguageProfile,
        default_threshold: float = THRESHOLD_BALANCED,
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

        # Optional LRU cache. Keyed by (text, language_code) — threshold-free,
        # since confidence/severity/categories do not depend on the threshold.
        # is_toxic is re-derived per call for threshold overrides.
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
            ClassificationResult with is_toxic, severity, confidence,
            matched_terms, signals, categories.
        """
        if threshold is None:
            threshold = self.default_threshold

        # Cache lookup (threshold-free key)
        cache_key = (text, self.profile.language_code)
        if self._cache is not None:
            cached = self._cache.get(cache_key)
            if cached is not None:
                if cached.is_toxic == (cached.confidence >= threshold):
                    return cached
                return replace(cached, is_toxic=cached.confidence >= threshold)

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

    async def analyze_async(
        self,
        text: str,
        threshold: float | None = None,
    ) -> ClassificationResult:
        """
        Async wrapper around analyze() — runs the CPU-bound analysis in a
        worker thread so event-loop servers (FastAPI, aiohttp) stay responsive.
        """
        return await asyncio.to_thread(self.analyze, text, threshold)

    def is_toxic(self, text: str, threshold: float | None = None) -> bool:
        """Quick check: is the text toxic?"""
        return self.analyze(text, threshold).is_toxic

    def sanitize(self, text: str, mask: str = "*", threshold: float | None = None) -> str:
        """
        Sanitize text by masking toxic segments — including obfuscated surface
        forms (leetspeak, separators, repeated characters, homoglyphs, split
        words). Masking always covers exactly what analysis flagged.

        Args:
            text: Raw input text.
            mask: Character to use for masking (default: '*').
            threshold: Confidence threshold override.

        Returns:
            Text with toxic words/phrases replaced by mask characters.
            Clean text is returned unchanged.
        """
        result = self.analyze(text, threshold)
        if not result.is_toxic or not result.matched_terms:
            return text

        multi_terms = [t for t in result.matched_terms if " " in t]
        single_terms = {t for t in result.matched_terms if " " not in t}

        # ── Pass 1: multi-word phrases — mask the raw span (flexible spacing) ──
        sanitized = text
        for term in multi_terms:
            pattern = re.compile(
                r"\b" + r"\s+".join(re.escape(w) for w in term.split()) + r"\b",
                re.IGNORECASE,
            )
            sanitized = pattern.sub(lambda m: mask * len(m.group()), sanitized)

        if not single_terms:
            return sanitized

        tokens = _WS_SPLIT_RE.split(sanitized)  # keeps whitespace separators
        word_positions = [i for i, t in enumerate(tokens) if t.strip()]

        # ── Pass 2: per-token masking via normalized-form matching ────────────
        # A raw token is masked when any of its normalized variants (primary,
        # leet-alternative, aggressive) resolves to a matched term — exactly,
        # stemmed, joined, or within edit distance 1 (mirrors the classifier).
        normalized_tokens: dict[int, str] = {}
        for i in word_positions:
            tok = tokens[i]
            hit = False
            for variant in self.normalizer.normalize_with_alternatives(tok):
                if not variant:
                    continue
                parts = variant.split()
                candidates = parts + ["".join(parts)] if len(parts) > 1 else parts
                for cand in candidates:
                    if cand in single_terms or self.profile.stemmer.stem(cand) in single_terms:
                        hit = True
                        break
                    if len(cand) >= 5:
                        for term in single_terms:
                            if (
                                len(term) >= 5
                                and abs(len(cand) - len(term)) <= 1
                                and _edit_distance_1(cand, term)
                            ):
                                hit = True
                                break
                    if hit:
                        break
                if hit:
                    break
            if hit:
                tokens[i] = mask * len(tok)
            # Record the compact normalized form for the concat pass below.
            normalized_tokens[i] = self.normalizer.normalize(tok).replace(" ", "")

        # ── Pass 3: split-word concat masking ("f u c k" → term "fuck") ───────
        # Mirrors the classifier's concat signal: windows of 2–5 consecutive
        # short tokens whose joined normalization contains a matched term.
        # Only the tokens of the actually-matching window are masked.
        live = [i for i in word_positions if not set(tokens[i]) <= set(mask)]

        # Maximal runs of consecutive short (normalized length ≤ 3) tokens
        runs: list[list[int]] = []
        run: list[int] = []
        for i in live:
            norm = normalized_tokens.get(i, "")
            if norm and len(norm) <= 3:
                run.append(i)
            else:
                if len(run) >= 2:
                    runs.append(run)
                run = []
        if len(run) >= 2:
            runs.append(run)

        for r in runs:
            n = len(r)
            for start in range(n):
                max_size = min(5, n - start)
                for size in range(2, max_size + 1):
                    window = r[start: start + size]
                    concatenated = "".join(normalized_tokens[j] for j in window)
                    if any(term in concatenated for term in single_terms):
                        for j in window:
                            if not set(tokens[j]) <= set(mask):
                                tokens[j] = mask * len(tokens[j])
                        break

        return "".join(tokens)

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

    async def batch_analyze_async(
        self,
        texts: list[str],
        threshold: float | None = None,
    ) -> list[ClassificationResult]:
        """Async wrapper around batch_analyze() (runs in a worker thread)."""
        return await asyncio.to_thread(self.batch_analyze, texts, threshold)

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

        # Try alternative normalizations (leet alternatives, aggressive collapse).
        # The primary variant is passed in so it is not recomputed.
        variants = self.normalizer.normalize_with_alternatives(text, primary=normalized)
        for variant in variants[1:]:  # skip primary (already tried)
            tokens = self.tokenizer.tokenize(variant)
            variant_result = self.classifier.classify(tokens, self.profile, threshold)
            if variant_result.is_toxic:
                return variant_result
            # Keep the best result if nothing is toxic
            if variant_result.confidence > result.confidence:
                result = variant_result

        return result
