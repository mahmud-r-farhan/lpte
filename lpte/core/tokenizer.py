"""
Tokenizer — segments normalized text into analyzable tokens.

Supports:
- Word-boundary splitting
- CJK (Chinese, Japanese, Korean) sub-phrase and n-gram segmentation
- Word-level n-gram generation (bigrams, trigrams)
- Character-level n-gram generation for obfuscation detection
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class TokenizationResult:
    """Result of tokenizing a text string."""

    words: list[str]
    bigrams: list[str]
    trigrams: list[str]
    raw_normalized: str


def _is_cjk_char(c: str) -> bool:
    """Check if character is a CJK ideograph."""
    code = ord(c)
    return (
        0x4E00 <= code <= 0x9FFF   # CJK Unified Ideographs
        or 0x3400 <= code <= 0x4DBF  # CJK Unified Ideographs Extension A
        or 0x20000 <= code <= 0x2A6DF # Extension B
        or 0xF900 <= code <= 0xFAFF  # CJK Compatibility Ideographs
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

        # For CJK ideograms without spaces, generate character and n-gram tokens
        for w in base_words:
            if any(_is_cjk_char(c) for c in w):
                for n in range(1, min(len(w) + 1, 6)):
                    for i in range(len(w) - n + 1):
                        gram = w[i : i + n]
                        if gram not in words:
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
