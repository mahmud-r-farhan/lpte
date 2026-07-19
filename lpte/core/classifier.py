"""
Multi-signal toxicity classifier.

Scoring approach:
1. Exact root-word match → confidence 1.0
2. Stemmed match → confidence 0.85
3. Concatenated-word match (split bypasses) → confidence 0.7
4. Fuzzy match (edit distance ≤ 1) → confidence 0.65

Context rules suppress false positives: if a bad word has context rules
and the input word is a known clean variant, the match is skipped.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import IntEnum

from lpte.core.profile import LanguageProfile
from lpte.core.tokenizer import TokenizationResult


class Severity(IntEnum):
    """Toxicity severity levels."""

    NONE = 0
    LOW = 1
    MEDIUM = 2
    HIGH = 3
    CRITICAL = 4


@dataclass
class ClassificationResult:
    """Full result of a toxicity classification."""

    is_toxic: bool
    severity: Severity
    confidence: float
    matched_terms: list[str]
    signals: dict[str, int] = field(default_factory=dict)


def _edit_distance_1(s: str, t: str) -> bool:
    """Check if two strings differ by at most 1 edit (insert, delete, substitute)."""
    if abs(len(s) - len(t)) > 1:
        return False
    if len(s) > len(t):
        s, t = t, s
    i = j = 0
    edits = 0
    while i < len(s) and j < len(t):
        if s[i] == t[j]:
            i += 1
            j += 1
        else:
            edits += 1
            if edits > 1:
                return False
            if len(s) == len(t):
                i += 1
                j += 1
            else:
                j += 1
    return True


def _is_context_clean(word: str, bad_word: str, context_rules: dict[str, set[str]]) -> bool:
    """Check if a word is a known clean variant of a bad word (context rule)."""
    clean_words = context_rules.get(bad_word, set())
    return word in clean_words


class Classifier:
    """Classifies tokenized text against a language profile."""

    def classify(
        self,
        tokens: TokenizationResult,
        profile: LanguageProfile,
        threshold: float = 0.6,
    ) -> ClassificationResult:
        matched_terms: list[str] = []
        signals: dict[str, int] = {
            "exact_match": 0,
            "stemmed_match": 0,
            "concat_match": 0,
            "fuzzy_match": 0,
        }

        bad_words = profile.bad_words
        words = tokens.words
        context_rules = profile.context_rules

        # 1. Exact root-word matching (with context rule check)
        for word in words:
            root = profile.stemmer.stem(word)
            if root in bad_words or word in bad_words:
                matched_bad = root if root in bad_words else word
                if _is_context_clean(word, matched_bad, context_rules):
                    continue
                matched_terms.append(root)
                signals["exact_match"] += 1

        # 2. Stemmed matching (only if no exact matches)
        if not matched_terms:
            for word in words:
                stemmed = profile.stemmer.stem(word)
                if stemmed in bad_words:
                    if _is_context_clean(word, stemmed, context_rules):
                        continue
                    matched_terms.append(stemmed)
                    signals["stemmed_match"] += 1

        # 3. Concatenated-word detection (catches "f u c k" → "fuck")
        if not matched_terms and len(words) >= 2:
            for window_size in range(2, min(len(words) + 1, 6)):
                for i in range(len(words) - window_size + 1):
                    window = words[i : i + window_size]
                    if all(len(w) <= 3 for w in window):
                        concatenated = "".join(window)
                        for bad_word in bad_words:
                            if bad_word in concatenated:
                                matched_terms.append(bad_word)
                                signals["concat_match"] += 1
                                break

        # 4. Fuzzy matching — edit distance ≤ 1 (with context rule check)
        if not matched_terms:
            for word in words:
                if len(word) < 3:
                    continue
                for bad_word in bad_words:
                    if abs(len(word) - len(bad_word)) <= 1 and _edit_distance_1(word, bad_word):
                        if _is_context_clean(word, bad_word, context_rules):
                            continue
                        matched_terms.append(bad_word)
                        signals["fuzzy_match"] += 1
                        break

        # Calculate confidence with per-signal floors
        confidence = 0.0

        if signals["exact_match"] > 0:
            confidence = min(0.6 + signals["exact_match"] * 0.2, 1.0)

        if signals["stemmed_match"] > 0:
            confidence = max(confidence, min(0.5 + signals["stemmed_match"] * 0.2, 0.9))

        if signals["concat_match"] > 0:
            confidence = max(confidence, min(0.5 + signals["concat_match"] * 0.2, 0.85))

        if signals["fuzzy_match"] > 0:
            confidence = max(confidence, min(0.5 + signals["fuzzy_match"] * 0.15, 0.75))

        if confidence >= 0.9:
            severity = Severity.CRITICAL
        elif confidence >= 0.7:
            severity = Severity.HIGH
        elif confidence >= 0.4:
            severity = Severity.MEDIUM
        elif confidence > 0:
            severity = Severity.LOW
        else:
            severity = Severity.NONE

        return ClassificationResult(
            is_toxic=confidence >= threshold,
            severity=severity,
            confidence=confidence,
            matched_terms=list(set(matched_terms)),
            signals=signals,
        )
