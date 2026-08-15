"""
Text normalization pipeline.

Handles:
- Unicode NFKC normalization
- Zero-width / invisible character stripping (category-aware)
- Homoglyph normalization (for mixed-script Latin obfuscation: fаck → fuck)
- Leetspeak reversal (0→o, 1→i, @→a, $→s, etc.)
- Dot/dash separator collapsing for single-char sequences (f.u.c.k → fuck)
- Repeated character collapse
- Combining accent stripping (Latin/European diacritics)
- Case folding
- Universal multilingual character preservation (supports Indic, Arabic, Cyrillic, CJK, Latin)
"""

from __future__ import annotations

import re
import unicodedata


# ─── Leet Mappings ────────────────────────────────────────────────────────────

# Primary leet mappings (@ already covers 'a', so 4 → u for "f4ck" → "fuck")
_LEET_MAP: dict[str, str] = {
    "0": "o", "1": "i", "3": "e", "4": "u",
    "5": "s", "7": "t", "@": "a", "$": "s",
    "!": "i", "+": "t", "8": "b", "9": "g",
    "¥": "y", "€": "e", "£": "l",
}

# Alternative leet mappings for ambiguous chars (used in secondary pass)
_LEET_ALTERNATIVES: dict[str, list[str]] = {
    "4": ["a", "u"],     # "f4ck" could be "fuck" or "face"
    "@": ["a", "u"],     # "@" could map to either
}

# ─── Homoglyph Map ────────────────────────────────────────────────────────────
# Common Unicode homoglyphs used to obfuscate ASCII/Latin words
_HOMOGLYPH_MAP: dict[str, str] = {
    # Cyrillic lookalikes
    "а": "a", "е": "e", "о": "o", "р": "p", "с": "c", "х": "x",
    "у": "y", "і": "i", "ѕ": "s", "ј": "j", "ԁ": "d",
    # Greek lookalikes
    "ο": "o", "ρ": "p", "ν": "v", "υ": "u", "α": "a", "ε": "e",
    # Latin Extended lookalikes
    "ı": "i", "ĺ": "l", "ľ": "l",
    # Mathematical / fullwidth
    "ａ": "a", "ｂ": "b", "ｃ": "c", "ｄ": "d", "ｅ": "e",
    "ｆ": "f", "ｇ": "g", "ｈ": "h", "ｉ": "i", "ｊ": "j",
    "ｋ": "k", "ｌ": "l", "ｍ": "m", "ｎ": "n", "ｏ": "o",
    "ｐ": "p", "ｑ": "q", "ｒ": "r", "ｓ": "s", "ｔ": "t",
    "ｕ": "u", "ｖ": "v", "ｗ": "w", "ｘ": "x", "ｙ": "y", "ｚ": "z",
}

# ─── Zero-width Characters ────────────────────────────────────────────────────
# Explicit set of known invisible Unicode characters
_ZERO_WIDTH_CHARS: frozenset[str] = frozenset({
    "\u200B",  # zero-width space
    "\u200C",  # zero-width non-joiner
    "\u200D",  # zero-width joiner
    "\u200E",  # left-to-right mark
    "\u200F",  # right-to-left mark
    "\u2060",  # word joiner
    "\uFEFF",  # zero-width no-break space (BOM)
    "\u00AD",  # soft hyphen
    "\u034F",  # combining grapheme joiner
    "\u2800",  # braille pattern blank
    "\u180E",  # mongolian vowel separator
    "\u00A0",  # non-breaking space → normalize to regular space
})

# Unicode "format" category — catches future invisible chars
_FORMAT_CATEGORY = "Cf"

# ─── Regex Patterns ───────────────────────────────────────────────────────────

# Latin combining accent pattern only (preserves Indic/Arabic combining marks)
_LATIN_ACCENT_RE = re.compile(
    r"[\u0300-\u036f\u1AB0-\u1AFF\u1DC0-\u1DFF\u20D0-\u20FF\uFE20-\uFE2F]"
)

# Repeated character patterns
_REPEAT_3PLUS_RE = re.compile(r"(.)\1{2,}")  # 3+ → 2
_REPEAT_2PLUS_RE = re.compile(r"(.)\1+")     # 2+ → 1 (aggressive)

# Dot/dash separator pattern for single-char sequences:
# Catches "f.u.c.k", "f-u-c-k", "f*u*c*k", "f_u_c_k"
_SEPARATOR_RE = re.compile(r"(?<=[a-zA-Z0-9])[.\-_*,|/\\](?=[a-zA-Z0-9])")


class TextNormalizer:
    """Normalizes raw text into canonical form for toxicity analysis."""

    def normalize(self, text: str) -> str:
        """
        Run the full normalization pipeline.
        Returns normalized lowercase string.
        """
        result = text

        # 1. Strip zero-width / invisible characters
        result = self._strip_zero_width(result)

        # 2. Homoglyph normalization (for mixed-script obfuscation only)
        result = self._apply_homoglyphs(result)

        # 3. Unicode NFC / Latin accent stripping
        result = _LATIN_ACCENT_RE.sub("", result)
        result = unicodedata.normalize("NFC", result)

        # 4. Leetspeak reversal
        result = self._apply_leet_reversal(result)

        # 5. Collapse dot/dash separators between single chars (f.u.c.k → fuck)
        result = self._strip_separators(result)

        # 6. Collapse repeated characters (3+ → 2)
        result = _REPEAT_3PLUS_RE.sub(r"\1\1", result)

        # 7. Multilingual sanitization: keep letters, digits, and combining marks
        result = self._sanitize_multilingual(result)

        # 8. Lowercase
        result = result.lower()

        # 9. Collapse multiple spaces
        result = " ".join(result.split())

        return result.strip()

    def normalize_aggressive(self, text: str) -> str:
        """
        Aggressive normalization — collapses ALL repeated chars to 1.
        Used as a secondary pass when primary normalization doesn't match.
        """
        result = self.normalize(text)
        result = _REPEAT_2PLUS_RE.sub(r"\1", result)
        return result.strip()

    def normalize_with_alternatives(self, text: str) -> list[str]:
        """
        Generate multiple normalized variants using alternative leet mappings.
        Returns list of variants to try (primary first, then alternatives).
        """
        variants = [self.normalize(text)]

        # Find chars that have alternatives
        alt_chars = set()
        for c in text:
            if c in _LEET_ALTERNATIVES:
                alt_chars.add(c)

        if alt_chars:
            # Generate variants with one alternative at a time
            for alt_char in alt_chars:
                alt_map = _LEET_MAP.copy()
                alternatives = _LEET_ALTERNATIVES[alt_char]
                for alt in alternatives:
                    alt_map[alt_char] = alt
                    variant = text
                    variant = self._strip_zero_width(variant)
                    variant = self._apply_homoglyphs(variant)
                    variant = _LATIN_ACCENT_RE.sub("", variant)
                    variant = unicodedata.normalize("NFC", variant)
                    variant = "".join(alt_map.get(c, c) for c in variant)
                    variant = self._strip_separators(variant)
                    variant = _REPEAT_3PLUS_RE.sub(r"\1\1", variant)
                    variant = self._sanitize_multilingual(variant).lower().strip()
                    variant = " ".join(variant.split())
                    if variant and variant not in variants:
                        variants.append(variant)

        # Also add aggressive collapse variant
        aggressive = self.normalize_aggressive(text)
        if aggressive and aggressive not in variants:
            variants.append(aggressive)

        return variants

    # ─── Private Helpers ──────────────────────────────────────────────────────

    def _strip_zero_width(self, text: str) -> str:
        """Strip known invisible chars + Unicode Cf (format) category."""
        result = []
        for c in text:
            if c in _ZERO_WIDTH_CHARS:
                continue
            if unicodedata.category(c) == _FORMAT_CATEGORY:
                continue
            # Normalize non-breaking space to regular space
            if c == "\u00A0":
                result.append(" ")
            else:
                result.append(c)
        return "".join(result)

    def _apply_homoglyphs(self, text: str) -> str:
        """
        Apply homoglyph mappings to words that mix Latin letters with lookalikes
        (e.g., 'fаck' with Cyrillic 'а'). Avoids altering pure Cyrillic/Greek text.
        """
        words = text.split()
        normalized_words = []
        for w in words:
            # Check if word has Latin characters alongside lookalikes
            has_latin = any("a" <= c.lower() <= "z" for c in w)
            has_fullwidth = any(0xFF00 <= ord(c) <= 0xFFEF for c in w)
            if has_latin or has_fullwidth:
                w = "".join(_HOMOGLYPH_MAP.get(c, c) for c in w)
            normalized_words.append(w)
        return " ".join(normalized_words)

    def _apply_leet_reversal(self, text: str) -> str:
        return "".join(_LEET_MAP.get(c, c) for c in text)

    def _strip_separators(self, text: str) -> str:
        """
        Remove punctuation separators between letters in single-char sequences.
        e.g.: 'f.u.c.k' → 'fuck', 'f-u-c-k' → 'fuck'
        """
        return _SEPARATOR_RE.sub("", text)

    def _sanitize_multilingual(self, text: str) -> str:
        """
        Preserve letters (L), numbers (N), and combining marks (M) across all scripts.
        Punctuation and non-word symbols are converted to spaces.
        """
        res = []
        for c in text:
            cat = unicodedata.category(c)
            if cat[0] in ("L", "N", "M"):
                res.append(c)
            else:
                res.append(" ")
        return "".join(res)
