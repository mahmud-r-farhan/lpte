"""Tokenization with stable normalized-text offsets.

For unspaced Han/Kana text we generate only the character-window lengths
present in the engine's vocabulary (the public default remains 1..5).
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field

_WORD_RE = re.compile(r"\S+")


@dataclass(frozen=True)
class TokenizationResult:
    words: list[str]
    bigrams: list[str]
    trigrams: list[str]
    raw_normalized: str
    word_spans: list[tuple[int, int]] = field(default_factory=list)
    base_count: int = 0


def _is_cjk_or_kana(c: str) -> bool:
    code = ord(c)
    return (
        0x4E00 <= code <= 0x9FFF
        or 0x3040 <= code <= 0x30FF
        or 0x31F0 <= code <= 0x31FF
        or 0x3400 <= code <= 0x4DBF
        or 0xF900 <= code <= 0xFAFF
        or 0x20000 <= code <= 0x2FA1F
    )


class Tokenizer:
    def __init__(self, cjk_lengths: tuple[int, ...] | None = None) -> None:
        self.cjk_lengths = cjk_lengths if cjk_lengths is not None else (1, 2, 3, 4, 5)

    def tokenize(self, normalized_text: str) -> TokenizationResult:
        base = list(_WORD_RE.finditer(normalized_text))
        base_words = [m.group() for m in base]
        words = list(base_words)
        spans = [m.span() for m in base]
        for match in base if self.cjk_lengths else ():
            w = match.group()
            if not any(_is_cjk_or_kana(c) for c in w):
                continue
            for length in self.cjk_lengths:
                if length > len(w):
                    continue
                for i in range(len(w) - length + 1):
                    # The entire token has already been added above.
                    if i == 0 and length == len(w):
                        continue
                    words.append(w[i : i + length])
                    spans.append((match.start() + i, match.start() + i + length))
        return TokenizationResult(
            words,
            self._generate_ngrams(base_words, 2),
            self._generate_ngrams(base_words, 3),
            normalized_text,
            spans,
            len(base),
        )

    def character_ngrams(self, word: str, min_n: int = 2, max_n: int = 4) -> list[str]:
        return [word[i : i + n] for n in range(min_n, max_n + 1) for i in range(len(word) - n + 1)]

    @staticmethod
    def _split_words(text: str) -> list[str]:
        return text.split()

    @staticmethod
    def _generate_ngrams(words: list[str], n: int) -> list[str]:
        return [" ".join(words[i : i + n]) for i in range(len(words) - n + 1)]
