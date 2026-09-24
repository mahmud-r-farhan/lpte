"""Multilingual, obfuscation-aware normalization (and optional source offsets).

The fast string-only path is used during analysis. The offset-preserving path
runs only for sanitization, where mapping a detected normalized token back to
its original surface form is essential (f4ck, f.u.c.k, zero-width, etc.).
"""

from __future__ import annotations

import re
import unicodedata
from dataclasses import dataclass
from functools import lru_cache

_LEET_MAP = {
    "0": "o",
    "1": "i",
    "3": "e",
    "4": "u",
    "5": "s",
    "7": "t",
    "@": "a",
    "$": "s",
    "8": "b",
    "9": "g",
    "¥": "y",
    "€": "e",
    "£": "l",
}
_LEET_TRANSLATE = str.maketrans(_LEET_MAP)
_LEET_ALTERNATIVES = {"4": "a", "@": "u"}
_ALT_TRANSLATE = {
    key: str.maketrans({**_LEET_MAP, key: value}) for key, value in _LEET_ALTERNATIVES.items()
}
_INLINE_LEET_RE = re.compile(r"(?<=[a-zA-Z0-9])[!+](?=[a-zA-Z0-9])")
_HOMOGLYPH_MAP = {
    "а": "a",
    "е": "e",
    "о": "o",
    "р": "p",
    "с": "c",
    "х": "x",
    "у": "y",
    "і": "i",
    "ѕ": "s",
    "ј": "j",
    "ԁ": "d",
    "ο": "o",
    "ρ": "p",
    "ν": "v",
    "υ": "u",
    "α": "a",
    "ε": "e",
    "ı": "i",
    "ĺ": "l",
    "ľ": "l",
    **{chr(i): chr(i - 0xFF41 + ord("a")) for i in range(0xFF41, 0xFF5B)},
    **{chr(i): chr(i - 0xFF21 + ord("a")) for i in range(0xFF21, 0xFF3B)},
}
_HOMOGLYPH_TRANSLATE = str.maketrans(_HOMOGLYPH_MAP)
_ZERO_WIDTH = frozenset(
    {
        "\u200b",
        "\u200c",
        "\u200d",
        "\u200e",
        "\u200f",
        "\u2060",
        "\ufeff",
        "\u00ad",
        "\u034f",
        "\u2800",
        "\u180e",
    }
)
_REPEAT_3 = re.compile(r"([^\W\d_])\1{2,}")  # avoid repeated digits in IDs
_REPEAT_2 = re.compile(r"([^\W\d_])\1+")
# Only remove separators in isolated sequences of single characters, not in
# ordinary punctuation, domains or hyphenated words such as 'kill-the-process'.
_SEPARATORS = frozenset(".-_*,|/\\")
_SEPARATED_LETTERS = re.compile(
    r"(?<![A-Za-z0-9])(?:[A-Za-z0-9][.\-_*,|/\\]){2,}[A-Za-z0-9](?![A-Za-z0-9])"
)
_NONSPACE = re.compile(r"\S+")


@lru_cache(maxsize=4096)
def _category(c: str) -> str:
    return unicodedata.category(c)


@dataclass(frozen=True)
class NormalizedText:
    text: str
    # One half-open [start, end) range in the original string per output char.
    offsets: tuple[tuple[int, int], ...]

    def original_span(self, start: int, end: int) -> tuple[int, int]:
        indices = self.offsets[start:end]
        if not indices:
            raise ValueError("empty normalized match")
        return min(a for a, _ in indices), max(b for _, b in indices)


def _homoglyphs(word: str) -> str:
    if word.isascii():
        return word
    if any(("a" <= c.lower() <= "z") or (0xFF00 <= ord(c) <= 0xFFEF) for c in word):
        return word.translate(_HOMOGLYPH_TRANSLATE)
    return word


def _separators(text: str) -> str:
    return _SEPARATED_LETTERS.sub(
        lambda m: "".join(c for c in m.group() if c not in _SEPARATORS), text
    )


def _has_alternative(text: str, symbol: str) -> bool:
    # Do not try another reading for the numeric suffix of an ID (word4),
    # but allow leading/embedded obfuscation (4ss, f4ck, @ss, f@ck).
    for i, c in enumerate(text):
        if (
            c != symbol
            or i + 1 == len(text)
            or not text[i + 1].isascii()
            or not text[i + 1].isalpha()
        ):
            continue
        if i and text[i - 1].isascii() and text[i - 1].isalpha():
            return True
        if (
            (i == 0 or not text[i - 1].isalnum())
            and i + 2 < len(text)
            and text[i + 2].isascii()
            and text[i + 2].isalpha()
        ):
            return True
    return False


class TextNormalizer:
    """Canonicalize text without transliterating natural non-Latin scripts."""

    def normalize(self, text: str) -> str:
        return self._normalize(text)

    def normalize_aggressive(self, text: str) -> str:
        return self._normalize(text, aggressive=True)

    def normalize_with_alternatives(self, text: str) -> list[str]:
        """Try alternate leet readings and triple-letter collapse when relevant."""
        variants = [self.normalize(text)]
        for c in _LEET_ALTERNATIVES:
            if _has_alternative(text, c):
                variants.append(self._normalize(text, alternative=c))
        if _REPEAT_3.search(text):
            variants.append(self.normalize_aggressive(text))
        return list(dict.fromkeys(variants))

    def normalize_variants_with_spans(self, text: str) -> list[NormalizedText]:
        """Produce the same variants as above, this time with raw offsets."""
        variants = [self._with_spans(text)]
        for c in _LEET_ALTERNATIVES:
            if _has_alternative(text, c):
                variants.append(self._with_spans(text, alternative=c))
        if _REPEAT_3.search(text):
            variants.append(self._with_spans(text, aggressive=True))
        seen: set[str] = set()
        unique = []
        for variant in variants:
            if variant.text not in seen:
                unique.append(variant)
                seen.add(variant.text)
        return unique

    def _normalize(self, text: str, *, alternative: str = "", aggressive: bool = False) -> str:
        text = "".join(
            " " if c == "\u00a0" else c
            for c in text
            if c not in _ZERO_WIDTH and _category(c) != "Cf"
        )
        text = " ".join(_homoglyphs(w) for w in text.split())
        # Compose decomposed accents; stripping them would turn Spanish 'año'
        # into 'ano' and make dictionary matches depend on input encoding.
        text = unicodedata.normalize("NFC", text)
        text = text.translate(_ALT_TRANSLATE[alternative] if alternative else _LEET_TRANSLATE)
        text = _INLINE_LEET_RE.sub(lambda m: "i" if m.group() == "!" else "t", text)
        text = _separators(text)
        text = (_REPEAT_2 if aggressive else _REPEAT_3).sub(
            (lambda m: m.group(1)) if aggressive else (lambda m: m.group(1) * 2), text
        )
        text = "".join(c if _category(c)[0] in "LNM" else " " for c in text)
        return " ".join(text.lower().split())

    def _with_spans(
        self, text: str, *, alternative: str = "", aggressive: bool = False
    ) -> NormalizedText:
        # Parallel (character, source range) arrays keep every transformation
        # aligned, including length-changing ones. Only used when masking.
        chars: list[tuple[str, int, int]] = []
        for i, c in enumerate(text):
            if c in _ZERO_WIDTH or _category(c) == "Cf":
                continue
            chars.append((" " if c == "\u00a0" else c, i, i + 1))

        value = "".join(c for c, _, _ in chars)
        for match in _NONSPACE.finditer(value):
            word = match.group()
            changed = _homoglyphs(word)
            for i, c in enumerate(changed):
                _, a, b = chars[match.start() + i]
                chars[match.start() + i] = (c, a, b)
        # NFC may compose base+combining sequences. Attribute the composed
        # character to the full input range so nothing evades the mask.
        groups: list[list[tuple[str, int, int]]] = []
        for item in chars:
            if groups and _category(item[0])[0] == "M":
                groups[-1].append(item)
            else:
                groups.append([item])
        chars = []
        for group in groups:
            norm = unicodedata.normalize("NFC", "".join(c for c, _, _ in group))
            for c in norm:
                chars.append((c, group[0][1], group[-1][2]))

        # The fast path decides whether !/+ is inline *after* translating
        # neighbouring symbols (e.g. @!t -> a!t). Use the same view here.
        pre_leet = "".join(
            _LEET_ALTERNATIVES[alternative] if c == alternative else _LEET_MAP.get(c, c)
            for c, _, _ in chars
        )
        inline_positions = {m.start() for m in _INLINE_LEET_RE.finditer(pre_leet)}
        chars = [
            (("i" if c == "!" else "t"), a, b)
            if i in inline_positions
            else (
                (_LEET_ALTERNATIVES[alternative] if c == alternative else _LEET_MAP.get(c, c)),
                a,
                b,
            )
            for i, (c, a, b) in enumerate(chars)
        ]
        value = "".join(c for c, _, _ in chars)
        to_remove = set()
        for m in _SEPARATED_LETTERS.finditer(value):
            to_remove.update(i for i in range(m.start(), m.end()) if value[i] in _SEPARATORS)
        chars = [item for i, item in enumerate(chars) if i not in to_remove]
        value = "".join(c for c, _, _ in chars)
        matches = list((_REPEAT_2 if aggressive else _REPEAT_3).finditer(value))
        for m in reversed(matches):
            start, end = m.span()
            original = chars[start:end]
            if aggressive:
                chars[start:end] = [(original[0][0], original[0][1], original[-1][2])]
            else:
                chars[start:end] = [original[0], (original[1][0], original[1][1], original[-1][2])]
        chars = [(c if _category(c)[0] in "LNM" else " ", a, b) for c, a, b in chars]
        chars = [(lc, a, b) for c, a, b in chars for lc in c.lower()]

        # Collapse whitespace just like ' '.join(text.split()).
        out: list[tuple[str, int, int]] = []
        for m in _NONSPACE.finditer("".join(c for c, _, _ in chars)):
            if out:
                out.append((" ", out[-1][2], chars[m.start()][1]))
            out.extend(chars[m.start() : m.end()])
        return NormalizedText("".join(c for c, _, _ in out), tuple((a, b) for _, a, b in out))
