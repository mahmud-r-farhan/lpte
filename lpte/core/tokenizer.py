"""
Tokenizer — segments normalized text into analyzable tokens.

Supports:
- Word-boundary splitting
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
        words = self._split_words(normalized_text)
        bigrams = self._generate_ngrams(words, 2)
        trigrams = self._generate_ngrams(words, 3)

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


# Module-level singleton
tokenizer = Tokenizer()
