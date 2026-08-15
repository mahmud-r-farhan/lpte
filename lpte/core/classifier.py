"""
Multi-signal toxicity classifier.

Scoring approach:
1. Exact / stemmed match (merged single loop) → confidence 1.0 / 0.85
2. Phrase match (bigrams/trigrams vs bad_word phrases) → confidence 0.80
3. Concatenated-word match (split bypasses like "f u c k") → confidence 0.70
4. Fuzzy match (edit distance ≤ 1) → confidence 0.65

Context rules suppress false positives: if a bad word has context rules
and the input word is a known clean variant, the match is skipped.

min_word_length from LanguageProfile is enforced before any matching.
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


# ─── Helpers ──────────────────────────────────────────────────────────────────

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


def _is_context_clean(
    word: str,
    bad_word: str,
    context_rules: dict[str, set[str]],
    raw_text: str = "",
) -> bool:
    """Check if a word is a known clean variant or inside a clean compound word."""
    clean_words = context_rules.get(bad_word, set())
    if not clean_words:
        return False
    if word in clean_words:
        return True
    if raw_text and any(clean in raw_text for clean in clean_words):
        return True
    return False


# ─── Classifier ───────────────────────────────────────────────────────────────

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
            "phrase_match": 0,
            "concat_match": 0,
            "fuzzy_match": 0,
        }

        bad_words = profile.bad_words
        min_len = profile.min_word_length
        context_rules = profile.context_rules
        raw_text = tokens.raw_normalized

        # Filter words by min_word_length for exact/stemmed matching
        words = [w for w in tokens.words if len(w) >= min_len]
        # Keep ALL words (including single chars) for concat detection
        all_words = tokens.words

        # ── Signal 1: Exact + Stemmed match (single merged loop) ──────────────
        # Stem each word once and check both the stemmed and original forms.
        for word in words:
            stemmed = profile.stemmer.stem(word)

            if word in bad_words:
                if not _is_context_clean(word, word, context_rules, raw_text):
                    matched_terms.append(word)
                    signals["exact_match"] += 1
                    continue

            if stemmed != word and stemmed in bad_words:
                if not _is_context_clean(word, stemmed, context_rules, raw_text):
                    matched_terms.append(stemmed)
                    signals["stemmed_match"] += 1

        # ── Signal 2: Phrase match — bigrams and trigrams vs bad word set ──────
        # This catches multi-word toxic phrases not caught by single-word matching.
        if not matched_terms:
            all_ngrams = tokens.bigrams + tokens.trigrams
            for ngram in all_ngrams:
                # Check the raw n-gram and its stemmed components
                ngram_joined = ngram.replace(" ", "")
                if ngram in bad_words or ngram_joined in bad_words:
                    matched_bad = ngram if ngram in bad_words else ngram_joined
                    if not _is_context_clean(ngram, matched_bad, context_rules, raw_text):
                        matched_terms.append(ngram)
                        signals["phrase_match"] += 1
                        break
                # Also try stemming each word in the n-gram
                ngram_words = ngram.split()
                stemmed_ngram = " ".join(profile.stemmer.stem(w) for w in ngram_words)
                if stemmed_ngram in bad_words:
                    if not _is_context_clean(ngram, stemmed_ngram, context_rules, raw_text):
                        matched_terms.append(stemmed_ngram)
                        signals["phrase_match"] += 1
                        break

        # ── Signal 3: Concatenated-word detection ("f u c k" → "fuck") ─────────
        # Uses all_words (unfiltered) so single-char split words are included.
        if not matched_terms and len(all_words) >= 2:
            for window_size in range(2, min(len(all_words) + 1, 6)):
                found = False
                for i in range(len(all_words) - window_size + 1):
                    window = all_words[i: i + window_size]
                    # Only try windows of short single-char/double-char words
                    if all(len(w) <= 3 for w in window):
                        concatenated = "".join(window)
                        for bad_word in bad_words:
                            if bad_word in concatenated:
                                if not _is_context_clean(concatenated, bad_word, context_rules, raw_text):
                                    matched_terms.append(bad_word)
                                    signals["concat_match"] += 1
                                    found = True
                                    break
                    if found:
                        break
                if found:
                    break

        # ── Signal 4: Fuzzy matching — edit distance ≤ 1 ─────────────────────
        # Require both word and bad_word to be >= 5 chars to avoid false
        # positives from short common words ("today", "you", "are", etc.).
        if not matched_terms:
            for word in words:
                if len(word) < 5:
                    continue
                for bad_word in bad_words:
                    if len(bad_word) < 5:
                        continue
                    if abs(len(word) - len(bad_word)) <= 1 and _edit_distance_1(word, bad_word):
                        if _is_context_clean(word, bad_word, context_rules, raw_text):
                            continue
                        matched_terms.append(bad_word)
                        signals["fuzzy_match"] += 1
                        break

        # ── Confidence calculation ─────────────────────────────────────────────
        confidence = 0.0

        if signals["exact_match"] > 0:
            confidence = min(0.6 + signals["exact_match"] * 0.2, 1.0)

        if signals["stemmed_match"] > 0:
            confidence = max(confidence, min(0.5 + signals["stemmed_match"] * 0.2, 0.9))

        if signals["phrase_match"] > 0:
            confidence = max(confidence, min(0.5 + signals["phrase_match"] * 0.2, 0.85))

        if signals["concat_match"] > 0:
            confidence = max(confidence, min(0.5 + signals["concat_match"] * 0.2, 0.85))

        if signals["fuzzy_match"] > 0:
            confidence = max(confidence, min(0.5 + signals["fuzzy_match"] * 0.15, 0.75))

        # ── Severity mapping ──────────────────────────────────────────────────
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
