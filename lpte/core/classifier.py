"""Indexed, deterministic rule-based classification.

Detection is deliberately distinct from moderation policy. A confidence is a
rule score, NOT a calibrated probability of abuse. In particular, a single
exact vocabulary match scores 0.8; category and policy determine its impact.
"""

from __future__ import annotations

import math
from collections import defaultdict
from dataclasses import dataclass, field
from enum import IntEnum
from functools import lru_cache

from lpte.core.profile import CATEGORIES, LanguageProfile
from lpte.core.tokenizer import TokenizationResult, Tokenizer, _is_cjk_or_kana

SIGNAL_NAMES = (
    "exact_match",
    "stemmed_match",
    "phrase_match",
    "concat_match",
    "alias_match",
    "fuzzy_match",
)


class Severity(IntEnum):
    NONE = 0
    LOW = 1
    MEDIUM = 2
    HIGH = 3
    CRITICAL = 4


@dataclass(frozen=True)
class TermMatch:
    """Canonical term and position in one normalized variant of the input."""

    term: str
    category: str
    signal: str
    start: int
    end: int
    variant: int = 0
    language: str = ""


@dataclass
class ClassificationResult:
    is_toxic: bool
    severity: Severity
    confidence: float
    matched_terms: list[str]
    signals: dict[str, int] = field(default_factory=dict)
    categories: list[str] = field(default_factory=list)
    language: str = ""
    matches: tuple[TermMatch, ...] = field(default_factory=tuple, repr=False, compare=False)

    def at_threshold(self, threshold: float) -> ClassificationResult:
        """A fresh result: cached evidence cannot be mutated by a caller."""
        validate_threshold(threshold)
        return ClassificationResult(
            bool(self.confidence and self.confidence >= threshold),
            self.severity,
            self.confidence,
            list(self.matched_terms),
            dict(self.signals),
            list(self.categories),
            self.language,
            self.matches,
        )


def validate_threshold(value: float) -> None:
    if (
        isinstance(value, bool)
        or not isinstance(value, (int, float))
        or not math.isfinite(value)
        or not 0 <= value <= 1
    ):
        raise ValueError("threshold must be a finite number between 0.0 and 1.0")


def confidence_from_signals(signals: dict[str, int]) -> float:
    """Same scoring function for a full result and policy-filtered matches."""
    return max(
        min(0.6 + signals.get("exact_match", 0) * 0.2, 1.0)
        if signals.get("exact_match", 0)
        else 0.0,
        min(0.5 + signals.get("stemmed_match", 0) * 0.2, 0.9)
        if signals.get("stemmed_match", 0)
        else 0.0,
        min(0.5 + signals.get("phrase_match", 0) * 0.2, 0.85)
        if signals.get("phrase_match", 0)
        else 0.0,
        min(0.5 + signals.get("concat_match", 0) * 0.2, 0.85)
        if signals.get("concat_match", 0)
        else 0.0,
        min(0.5 + signals.get("alias_match", 0) * 0.25, 0.9)
        if signals.get("alias_match", 0)
        else 0.0,
        min(0.5 + signals.get("fuzzy_match", 0) * 0.15, 0.75)
        if signals.get("fuzzy_match", 0)
        else 0.0,
    )


def severity_for(confidence: float, categories: set[str]) -> Severity:
    if not confidence:
        return Severity.NONE
    if categories & {"slur", "threat"}:
        return Severity.CRITICAL
    if confidence >= 0.7:
        return Severity.HIGH
    if confidence >= 0.4:
        return Severity.MEDIUM
    return Severity.LOW


def _edit_distance_1(s: str, t: str) -> bool:
    if abs(len(s) - len(t)) > 1:
        return False
    if len(s) > len(t):
        s, t = t, s
    i = j = errors = 0
    while i < len(s) and j < len(t):
        if s[i] == t[j]:
            i += 1
            j += 1
        else:
            errors += 1
            if errors > 1:
                return False
            if len(s) == len(t):
                i += 1
                j += 1
            else:
                j += 1
    return True  # one trailing insertion/deletion is allowed


class _Rules:
    def __init__(self, profile: LanguageProfile):
        from lpte.core.normalizer import TextNormalizer

        self.words = frozenset(profile.bad_words)
        self.aliases = dict(profile.aliases)
        self.categories = dict(profile.word_categories)
        if (
            not self.words
            or set(self.categories) - self.words
            or set(self.aliases.values()) - self.words
        ):
            raise ValueError(
                "profile needs bad_words; categories and aliases must refer to bad_words"
            )
        if set(self.categories.values()) - CATEGORIES:
            raise ValueError("profile contains an unsupported word category")
        self.min_len = profile.min_word_length
        norm = TextNormalizer()
        self.context = {
            term: frozenset(norm.normalize(phrase) for phrase in phrases)
            for term, phrases in profile.context_rules.items()
        }
        self.stem = lru_cache(maxsize=4096)(profile.stemmer.stem)
        self.phrase_lengths = tuple(
            sorted({len(term.split()) for term in (*self.words, *self.aliases) if " " in term})
        )
        self.cjk_lengths = tuple(
            sorted(
                {
                    len(term)
                    for term in (*self.words, *self.aliases)
                    if " " not in term and any(_is_cjk_or_kana(c) for c in term)
                }
            )
        )
        # SymSpell-style deletion index. Lookup costs O(word length), rather
        # than scanning the full vocabulary for every unknown clean word.
        index: dict[str, set[str]] = defaultdict(set)
        for bad in self.words:
            if len(bad) < 5 or " " in bad or any(_is_cjk_or_kana(c) for c in bad):
                continue
            index[bad].add(bad)
            for i in range(len(bad)):
                index[bad[:i] + bad[i + 1 :]].add(bad)
        self.fuzzy_index = {k: tuple(sorted(v)) for k, v in index.items()}
        self.fuzzy = lru_cache(maxsize=4096)(self._fuzzy)

    def category(self, term: str) -> str:
        return self.categories.get(term, "profanity")

    def clean(self, term: str, surface: str, raw: str, start: int, end: int) -> bool:
        """Only a benign phrase *covering this occurrence* can suppress it."""
        for phrase in self.context.get(term, ()):
            if surface == phrase:
                return True
            pos = raw.find(phrase)
            while pos != -1:
                if pos <= start and end <= pos + len(phrase):
                    return True
                pos = raw.find(phrase, pos + 1)
        return False

    def _fuzzy(self, word: str) -> tuple[str, ...]:
        candidates: set[str] = set(self.fuzzy_index.get(word, ()))
        for i in range(len(word)):
            candidates.update(self.fuzzy_index.get(word[:i] + word[i + 1 :], ()))
        # Same first letter avoids e.g. French 'bonne' -> 'conne'.
        return tuple(
            bad for bad in sorted(candidates) if bad[0] == word[0] and _edit_distance_1(word, bad)
        )


class Classifier:
    """Compile indexes once per engine, then classify tokenized strings."""

    def __init__(self, profile: LanguageProfile | None = None):
        self._profile = profile
        self._rules = _Rules(profile) if profile is not None else None

    @property
    def cjk_lengths(self) -> tuple[int, ...]:
        return self._rules.cjk_lengths if self._rules is not None else ()

    def classify(
        self,
        tokens: TokenizationResult,
        profile: LanguageProfile,
        threshold: float = 0.6,
    ) -> ClassificationResult:
        validate_threshold(threshold)
        rules = self._rules if profile is self._profile else _Rules(profile)
        assert rules is not None
        # TokenizationResult was public before offsets were added. Derive
        # positions for older callers constructing it by hand.
        if tokens.words and not tokens.word_spans:
            tokens = Tokenizer(rules.cjk_lengths).tokenize(tokens.raw_normalized)
        raw = tokens.raw_normalized
        found: list[TermMatch] = []
        spans = tokens.word_spans
        base_words = tokens.words[: tokens.base_count]
        base_spans = spans[: tokens.base_count]
        base_span_set = set(base_spans)

        def add(term: str, surface: str, signal: str, start: int, end: int) -> None:
            if not rules.clean(term, surface, raw, start, end):
                found.append(
                    TermMatch(
                        term,
                        rules.category(term),
                        signal,
                        start,
                        end,
                        language=profile.language_code,
                    )
                )

        for word, (start, end) in zip(tokens.words, spans):
            if len(word) < rules.min_len:
                continue
            if word in rules.words:
                add(word, word, "exact_match", start, end)
                continue
            alias = rules.aliases.get(word)
            if alias:
                add(alias, word, "alias_match", start, end)
                continue
            stem = rules.stem(word)
            if stem != word:
                if stem in rules.words:
                    add(stem, word, "stemmed_match", start, end)
                    continue
                if stem in rules.aliases:
                    add(rules.aliases[stem], word, "alias_match", start, end)
                    continue
            # Fuzzy applies to whole words, not CJK sub-windows. Using a
            # deletion index also handles single insertions/substitutions.
            if (
                len(word) >= 5
                and not any(_is_cjk_or_kana(c) for c in word)
                and (start, end) in base_span_set
            ):
                for bad in rules.fuzzy(word):
                    if not rules.clean(bad, word, raw, start, end):
                        add(bad, word, "fuzzy_match", start, end)
                        break

        # Phrases are checked even when another word matched: a slur/threat in
        # the same message must not be hidden by a harmless swearword.
        for length in rules.phrase_lengths:
            for i in range(len(base_words) - length + 1):
                surface = " ".join(base_words[i : i + length])
                stemmed = " ".join(rules.stem(w) for w in base_words[i : i + length])
                term = (
                    surface
                    if surface in rules.words
                    else stemmed
                    if stemmed in rules.words
                    else rules.aliases.get(surface) or rules.aliases.get(stemmed)
                )
                if term:
                    add(
                        term,
                        surface,
                        "phrase_match",
                        base_spans[i][0],
                        base_spans[i + length - 1][1],
                    )

        # Split-word bypasses: only join runs of short Latin chunks, and only
        # look up *whole* vocabulary entries (never substrings of clean text).
        for i in range(len(base_words)):
            joined = ""
            for end in range(i, min(i + 5, len(base_words))):
                part = base_words[end]
                if len(part) > 3 or not part.isascii() or not part.isalpha():
                    break
                joined += part
                if end == i or len(joined) < max(3, rules.min_len):
                    continue
                term = joined if joined in rules.words else rules.aliases.get(joined)
                if term:
                    add(term, joined, "concat_match", base_spans[i][0], base_spans[end][1])

        # Keep the longest match at a location; CJK sub-windows can otherwise
        # duplicate an exact compound and inflate its score. Preserve matches
        # with different categories (the higher-harm signal must not disappear).
        found.sort(key=lambda m: (m.start, -(m.end - m.start), m.term, m.signal))
        distinct: list[TermMatch] = []
        for match in found:
            if any(
                old.category == match.category and old.start <= match.start and match.end <= old.end
                for old in distinct
            ):
                continue
            distinct.append(match)
        signals = dict.fromkeys(SIGNAL_NAMES, 0)
        for match in distinct:
            signals[match.signal] += 1
        confidence = confidence_from_signals(signals)
        categories = list(dict.fromkeys(m.category for m in distinct))
        return ClassificationResult(
            bool(confidence and confidence >= threshold),
            severity_for(confidence, set(categories)),
            confidence,
            list(dict.fromkeys(m.term for m in distinct)),
            signals,
            categories,
            profile.language_code if distinct else "",
            tuple(distinct),
        )
