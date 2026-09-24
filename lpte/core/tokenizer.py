"""
Tokenizer — segments normalized text into analyzable tokens.

Supports:
- Word-boundary splitting
- CJK (Chinese, Japanese, Korean) sub-phrase and n-gram segmentation
- Word-level n-gram generation (bigrams, trigrams)
- Character-level n-gram generation for obfuscation detection

Performance notes:
- CJK detection uses a precompiled character-class regex (C-level scan)
  instead of a per-character Python range check.
- Sub-phrase de-duplication uses a set instead of an O(n) list scan.
"""

from __future__ import annotations

import re
from dataclasses import dataclass


@dataclass(frozen=True)
class TokenizationResult:
    """Result of tokenizing a text string."""

    words: list[str]
    bigrams: list[str]
    trigrams: list[str]
    raw_normalized: str


# CJK ideographs, Hiragana, Katakana (incl. phonetic extensions),
# Extension A and CJK Compatibility Ideographs.
_CJK_RE = re.compile(
    "["
    "\u3040-\u309F"      # Hiragana
    "\u30A0-\u30FF"      # Katakana
    "\u31F0-\u31FF"      # Katakana Phonetic Extensions
    "\u3400-\u4DBF"      # CJK Unified Ideographs Extension A
    "\u4E00-\u9FFF"      # CJK Unified Ideographs
    "\uF900-\uFAFF"      # CJK Compatibility Ideographs
    "\U00020000-\U0002A6DF"  # Extension B
    "]"
)


def _is_cjk_or_kana(c: str) -> bool:
    """Check if character is a CJK ideograph, Hiragana, or Katakana."""
    code = ord(c)
    return (
        0x4E00 <= code <= 0x9FFF     # CJK Unified Ideographs
        or 0x3040 <= code <= 0x309F  # Hiragana
        or 0x30A0 <= code <= 0x30FF  # Katakana
        or 0x31F0 <= code <= 0x31FF  # Katakana Phonetic Extensions
        or 0x3400 <= code <= 0x4DBF  # CJK Unified Ideographs Extension A
        or 0xF900 <= code <= 0xFAFF  # CJK Compatibility Ideographs
        or 0x20000 <= code <= 0x2A6DF # Extension B
    )


class Tokenizer:
    """Splits normalized text into tokens and n-grams."""

    def tokenize(self, normalized_text: str) -> TokenizationResult:
        """
        Tokenize normalized text.

        Args:
            normalized_text: Already-normalized lowercase text.

        Returns:
            TokenizationResult with words, bigrams, trigrams.
        """
        base_words = self._split_words(normalized_text)
        words = list(base_words)

        # For unspaced East Asian scripts (CJK/Kana), generate sub-phrase & n-gram tokens
        seen: set[str] | None = None
        for w in base_words:
            if _CJK_RE.search(w):
                if seen is None:
                    seen = set(words)
                max_n = min(len(w) + 1, 6)
                for n in range(1, max_n):
                    for i in range(len(w) - n + 1):
                        gram = w[i : i + n]
                        if gram not in seen:
                            seen.add(gram)
                            words.append(gram)

        bigrams = self._generate_ngrams(base_words, 2)
        trigrams = self._generate_ngrams(base_words, 3)

        return TokenizationResult(
            words=words,
            bigrams=bigrams,
            trigrams=trigrams,
            raw_normalized=normalized_text,
        )

    def character_ngrams(self, word: str, min_n: int = 2, max_n: int = 4) -> list[str]:
        """
        Generate character-level n-grams from a single word.

        Used for detecting partial obfuscation within words.
        """
        grams: list[str] = []
        for n in range(min_n, max_n + 1):
            if len(word) < n:
                continue
            for i in range(len(word) - n + 1):
                grams.append(word[i : i + n])
        return grams

    @staticmethod
    def _split_words(text: str) -> list[str]:
        return [w for w in text.split() if w]

    @staticmethod
    def _generate_ngrams(words: list[str], n: int) -> list[str]:
        if len(words) < n:
            return []
        return [" ".join(words[i : i + n]) for i in range(len(words) - n + 1)]
