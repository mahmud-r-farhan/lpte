"""Code-switched analysis with conservative Unicode script routing."""

from __future__ import annotations

import asyncio

from lpte.core.cache import LRUCache
from lpte.core.classifier import (
    SIGNAL_NAMES,
    ClassificationResult,
    severity_for,
    validate_threshold,
)
from lpte.core.engine import LpteEngine, _check_mask
from lpte.core.profile import LanguageProfile


def _script(c: str) -> str | None:
    value = ord(c)
    if (
        65 <= value <= 90
        or 97 <= value <= 122
        or 0x00C0 <= value <= 0x024F
        or 0xFF21 <= value <= 0xFF5A
    ):
        return "Latin"
    if 0x0400 <= value <= 0x052F:
        return "Cyrillic"
    if 0x0980 <= value <= 0x09FF:
        return "Bengali"
    if 0x0900 <= value <= 0x097F:
        return "Devanagari"
    if 0x0600 <= value <= 0x06FF:
        return "Arabic"
    if 0x3400 <= value <= 0x9FFF or 0x20000 <= value <= 0x2FA1F:
        return "Han"
    if 0x3040 <= value <= 0x30FF:
        return "Kana"
    if 0xAC00 <= value <= 0xD7AF or 0x1100 <= value <= 0x11FF:
        return "Hangul"
    if 0x0370 <= value <= 0x03FF:
        return "Greek"
    if c.isalpha():
        return "Other"
    return None


def scripts_in(text: str) -> frozenset[str]:
    return frozenset(script for c in text if (script := _script(c)) is not None)


class MultiLangEngine:
    """Runs only packs whose scripts appear in the text.

    Unknown scripts are never silently dropped: data-only packs can specify
    ``scripts``; otherwise scripts are inferred from words and aliases. If
    there is no detectable script, all packs are tried (e.g. symbol-only text).
    """

    def __init__(
        self,
        profiles: list[LanguageProfile],
        default_threshold: float = 0.6,
        cache_size: int = 512,
    ) -> None:
        validate_threshold(default_threshold)
        if not profiles or len({p.language_code for p in profiles}) != len(profiles):
            raise ValueError("supply at least one profile, without duplicate language codes")
        if type(cache_size) is not int or cache_size < 0:
            raise ValueError("cache_size must be a non-negative integer")
        self.default_threshold = default_threshold
        self.engines = {
            p.language_code: LpteEngine(p, default_threshold, cache_size) for p in profiles
        }
        self._scripts = {
            p.language_code: frozenset(p.scripts)
            if p.scripts
            else scripts_in(" ".join((*p.bad_words, *p.aliases)))
            for p in profiles
        }
        self._cache: LRUCache[str, ClassificationResult] | None = (
            LRUCache(cache_size) if cache_size else None
        )

    def _routed(self, text: str) -> list[LpteEngine]:
        scripts = scripts_in(text)
        if not scripts:
            return list(self.engines.values())
        return [
            engine
            for code, engine in self.engines.items()
            if not self._scripts[code] or self._scripts[code] & scripts
        ]

    def analyze(self, text: str, threshold: float | None = None) -> ClassificationResult:
        if not isinstance(text, str):
            raise TypeError("text must be a string")
        threshold = self.default_threshold if threshold is None else threshold
        validate_threshold(threshold)
        evidence = self._cache.get(text) if self._cache is not None else None
        if evidence is None:
            results = [e.analyze(text) for e in self._routed(text)]
            matches = tuple(m for r in results for m in r.matches)
            confidence = max((r.confidence for r in results), default=0.0)
            terms = list(dict.fromkeys(m.term for m in matches))
            categories = list(dict.fromkeys(m.category for m in matches))
            signals = {
                key: max((r.signals[key] for r in results), default=0) for key in SIGNAL_NAMES
            }
            evidence = ClassificationResult(
                bool(confidence and confidence >= self.default_threshold),
                severity_for(confidence, set(categories)),
                confidence,
                terms,
                signals,
                categories,
                "+".join(r.language for r in results if r.language),
                matches,
            )
            if self._cache is not None:
                self._cache.put(text, evidence)
        return evidence.at_threshold(threshold)

    def is_toxic(self, text: str, threshold: float | None = None) -> bool:
        return self.analyze(text, threshold).is_toxic

    def sanitize(self, text: str, mask: str = "*", threshold: float | None = None) -> str:
        _check_mask(mask)
        threshold = self.default_threshold if threshold is None else threshold
        if not self.analyze(text, threshold).is_toxic:
            return text
        covered = [False] * len(text)
        for engine in self._routed(text):
            masked = engine.sanitize(text, mask, threshold)
            for i, (original, replacement) in enumerate(zip(text, masked)):
                if original != replacement:
                    covered[i] = True
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
        return await asyncio.to_thread(self.analyze, text, threshold)

    async def batch_analyze_async(
        self,
        texts: list[str],
        threshold: float | None = None,
    ) -> list[ClassificationResult]:
        return await asyncio.to_thread(self.batch_analyze, texts, threshold)

    def clear_cache(self) -> None:
        if self._cache is not None:
            self._cache.clear()
        for engine in self.engines.values():
            engine.clear_cache()

    def cache_stats(self) -> dict[str, object] | None:
        return self._cache.stats() if self._cache is not None else None
