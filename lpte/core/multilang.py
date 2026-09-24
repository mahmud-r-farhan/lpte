"""
Multi-language engine for code-switched (mixed-script) text.

Real messages are rarely monolingual. In Bangladesh and India, chat is
routinely written in Bengali/Hindi mixed with English in the same sentence —
"তুই একদম idiot" or "yeh toh bilkul bakwas hai" — often in Latin script
("romanized"), where no single language pack catches the whole message.

MultiLangEngine solves this pragmatically:

1. **Script routing** — inspects the Unicode script of the input and only runs
   the engines that could plausibly match. Running all 11 packs on every
   message would be ~11x the cost; routing keeps the common single-language
   case at the cost of one engine.
2. **Union of signals** — each candidate engine's hits are merged, so a
   Bengali slur and an English insult in the same message are both caught.
3. **Worst-case severity wins** — escalation must never be diluted by
   averaging across languages.

Latin-script text is ambiguous by nature (English, Spanish, French, German all
use it), so Latin text is checked against every configured Latin-script
language, which is exactly the behaviour you want for romanized chat.
"""

from __future__ import annotations

import re
from dataclasses import replace

from lpte.core.cache import LRUCache
from lpte.core.classifier import ClassificationResult, Severity
from lpte.core.engine import LpteEngine
from lpte.core.profile import LanguageProfile

# ─── Script Detection ─────────────────────────────────────────────────────────

# Ordered (script range → language code) table for non-Latin scripts.
# Latin is handled separately because it maps to many languages.
_SCRIPT_RANGES: list[tuple[tuple[int, int], str]] = [
    ((0x0980, 0x09FF), "bn"),  # Bengali
    ((0x0900, 0x097F), "hi"),  # Devanagari (Hindi, Marathi, Nepali)
    ((0x0A00, 0x0A7F), "hi"),  # Gurmukhi (Punjabi) — Hindi engine fallback
    ((0x0400, 0x04FF), "ru"),  # Cyrillic
    ((0x0600, 0x06FF), "ar"),  # Arabic
    ((0x0750, 0x077F), "ar"),  # Arabic Supplement
    ((0x0590, 0x05FF), "ar"),  # Hebrew — Arabic engine fallback
    ((0x3040, 0x309F), "ja"),  # Hiragana
    ((0x30A0, 0x30FF), "ja"),  # Katakana
    ((0x31F0, 0x31FF), "ja"),  # Katakana phonetic extensions
    ((0xAC00, 0xD7AF), "ko"),  # Hangul syllables
    ((0x1100, 0x11FF), "ko"),  # Hangul Jamo
    ((0x4E00, 0x9FFF), "zh"),  # CJK unified ideographs
    ((0x3400, 0x4DBF), "zh"),  # CJK extension A
    ((0xF900, 0xFAFF), "zh"),  # CJK compatibility
]

# Languages written in Latin script — a Latin message could be any of these.
_LATIN_LANGUAGES = ("en", "es", "fr", "de", "id", "it", "pt", "tr", "vi")

_LATIN_RE = re.compile(r"[A-Za-z]")
_CJK_RE = re.compile(r"[\u4e00-\u9fff\u3400-\u4dbf\uf900-\ufaff]")


def detect_scripts(text: str) -> set[str]:
    """
    Return the set of language codes implied by the scripts present in text.

    Latin text yields every configured Latin language code, since Latin script
    alone cannot distinguish English from Spanish or French.
    """
    codes: set[str] = set()
    for ch in text:
        code = ord(ch)
        for (low, high), lang in _SCRIPT_RANGES:
            if low <= code <= high:
                codes.add(lang)
                break
    if _LATIN_RE.search(text):
        codes.update(_LATIN_LANGUAGES)
    return codes


class MultiLangEngine:
    """
    Runs several language engines over one text and merges their verdicts.

    Usage:
        from lpte.core.multilang import MultiLangEngine
        from lpte.languages import BengaliProfile, EnglishProfile

        engine = MultiLangEngine([BengaliProfile, EnglishProfile])
        result = engine.analyze("তুই একদম idiot")
        # → toxic, matched both the Bengali and the English term

    Args:
        profiles: Language profiles to consider. Script routing picks among
            them at analysis time.
        default_threshold: Confidence threshold for the merged result.
        cache_size: LRU cache capacity for merged results.
    """

    def __init__(
        self,
        profiles: list[LanguageProfile],
        default_threshold: float = 0.6,
        cache_size: int = 512,
    ):
        if not profiles:
            raise ValueError("MultiLangEngine requires at least one profile")
        self.profiles = list(profiles)
        self.default_threshold = default_threshold
        self.engines: dict[str, LpteEngine] = {
            p.language_code: LpteEngine(p, default_threshold=default_threshold, cache_size=0)
            for p in self.profiles
        }
        self._all_codes = set(self.engines)
        self._cache: LRUCache[tuple[str, float], ClassificationResult] | None = (
            LRUCache(capacity=cache_size) if cache_size > 0 else None
        )

    # ─── Public API ───────────────────────────────────────────────────────────

    def analyze(self, text: str, threshold: float | None = None) -> ClassificationResult:
        """
        Analyze code-switched text and return a single merged result.

        Only engines whose script appears in the text are executed.
        """
        if threshold is None:
            threshold = self.default_threshold

        cache_key = (text, threshold)
        if self._cache is not None:
            cached = self._cache.get(cache_key)
            if cached is not None:
                return cached

        per_language = self.analyze_all(text, threshold)
        merged = self._merge(per_language, threshold)

        if self._cache is not None:
            self._cache.put(cache_key, merged)
        return merged

    def analyze_all(
        self,
        text: str,
        threshold: float | None = None,
    ) -> dict[str, ClassificationResult]:
        """
        Run every *relevant* engine and return results keyed by language code.

        Engines whose script is absent from the text are skipped, so a purely
        Bengali message never pays for the English engine.
        """
        if threshold is None:
            threshold = self.default_threshold

        results: dict[str, ClassificationResult] = {}
        for code in self._candidate_languages(text):
            engine = self.engines[code]
            result = engine.analyze(text, threshold)
            if result.matched_terms:
                results[code] = replace(result, language=code)
        return results

    def is_toxic(self, text: str, threshold: float | None = None) -> bool:
        return self.analyze(text, threshold).is_toxic

    def sanitize(self, text: str, mask: str = "*", threshold: float | None = None) -> str:
        """
        Mask toxic spans using every relevant engine, in sequence.

        Engines are applied in a stable order (the order given at construction)
        so the output is deterministic.
        """
        if threshold is None:
            threshold = self.default_threshold
        sanitized = text
        for code in self._candidate_languages(sanitized):
            engine = self.engines[code]
            result = engine.analyze(sanitized, threshold)
            if result.is_toxic and result.matched_terms:
                sanitized = engine.sanitize(sanitized, mask=mask, threshold=threshold)
        return sanitized

    def clear_cache(self) -> None:
        if self._cache is not None:
            self._cache.clear()
        for engine in self.engines.values():
            engine.clear_cache()

    # ─── Internals ────────────────────────────────────────────────────────────

    def _candidate_languages(self, text: str) -> list[str]:
        """Engines to run, in construction order, filtered by detected script."""
        if not text or not text.strip():
            return []
        needed = detect_scripts(text) & self._all_codes
        # Preserve the caller's ordering for deterministic results.
        return [p.language_code for p in self.profiles if p.language_code in needed]

    @staticmethod
    def _merge(
        per_language: dict[str, ClassificationResult],
        threshold: float,
    ) -> ClassificationResult:
        """
        Merge per-language results: union of terms and categories,
        worst-case severity and highest confidence.
        """
        if not per_language:
            return ClassificationResult(
                is_toxic=False,
                severity=Severity.NONE,
                confidence=0.0,
                matched_terms=[],
                signals={},
                categories=[],
                language="",
            )

        matched_terms: list[str] = []
        categories: list[str] = []
        signals: dict[str, int] = {}
        confidence = 0.0
        severity = Severity.NONE

        for code, result in per_language.items():
            matched_terms.extend(result.matched_terms)
            categories.extend(result.categories)
            confidence = max(confidence, result.confidence)
            if result.severity > severity:
                severity = result.severity
            for key, value in result.signals.items():
                signals[key] = signals.get(key, 0) + value

        # Order-preserving dedupe keeps output deterministic.
        matched_terms = list(dict.fromkeys(matched_terms))
        categories = sorted(set(categories))

        return ClassificationResult(
            is_toxic=confidence >= threshold,
            severity=severity,
            confidence=confidence,
            matched_terms=matched_terms,
            signals=signals,
            categories=categories,
            language=",".join(per_language.keys()),
        )
