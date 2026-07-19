"""
Text normalization pipeline.

Handles:
- Unicode NFKC normalization
- Leetspeak reversal (0→o, 1→i, @→a, $→s, etc.)
- Zero-width character stripping
- Repeated character collapse
- Accent/diacritic stripping
- Case folding
"""

from __future__ import annotations

import re
import unicodedata


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

# Zero-width / invisible Unicode characters
_ZERO_WIDTH_CHARS: set[str] = {
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
}

# Bengali Unicode block range
_BENGALI_RANGE = (0x0980, 0x09FF)

# Accent/diacritic pattern (combining marks)
_ACCENT_RE = re.compile(r"[\u0300-\u036f\u1AB0-\u1AFF\u1DC0-\u1DFF\u20D0-\u20FF\uFE20-\uFE2F]")

# Repeated character patterns
_REPEAT_3PLUS_RE = re.compile(r"(.)\1{2,}")  # 3+ → 2
_REPEAT_2PLUS_RE = re.compile(r"(.)\1+")     # 2+ → 1 (aggressive)


class TextNormalizer:
    """Normalizes raw text into canonical form for toxicity analysis."""

    def normalize(self, text: str) -> str:
        """
        Run the full normalization pipeline.
        Returns normalized lowercase string.
        """
        result = text

        # 1. Strip zero-width characters
        result = self._strip_zero_width(result)

        # 2. Unicode NFKD normalization + accent stripping
        result = unicodedata.normalize("NFKD", result)
        result = _ACCENT_RE.sub("", result)
        result = unicodedata.normalize("NFC", result)

        # 3. Leetspeak reversal
        result = self._apply_leet_reversal(result)

        # 4. Collapse repeated characters (3+ → 2)
        result = _REPEAT_3PLUS_RE.sub(r"\1\1", result)

        # 5. Sanitize: keep letters, digits, Bengali block, spaces
        result = self._sanitize(result)

        # 6. Lowercase
        result = result.lower()

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
                    # Strip zero-width
                    variant = self._strip_zero_width(variant)
                    variant = unicodedata.normalize("NFKD", variant)
                    variant = _ACCENT_RE.sub("", variant)
                    variant = unicodedata.normalize("NFC", variant)
                    # Apply custom leet map
                    variant = "".join(alt_map.get(c, c) for c in variant)
                    variant = _REPEAT_3PLUS_RE.sub(r"\1\1", variant)
                    variant = self._sanitize(variant).lower().strip()
                    if variant and variant not in variants:
                        variants.append(variant)

        # Also add aggressive collapse variant
        aggressive = self.normalize_aggressive(text)
        if aggressive and aggressive not in variants:
            variants.append(aggressive)

        return variants

    def _strip_zero_width(self, text: str) -> str:
        return "".join(c for c in text if c not in _ZERO_WIDTH_CHARS)

    def _apply_leet_reversal(self, text: str) -> str:
        return "".join(_LEET_MAP.get(c, c) for c in text)

    def _sanitize(self, text: str) -> str:
        chars: list[str] = []
        for c in text:
            code = ord(c)
            if ("a" <= c <= "z") or ("A" <= c <= "Z") or ("0" <= c <= "9"):
                chars.append(c)
            elif _BENGALI_RANGE[0] <= code <= _BENGALI_RANGE[1]:
                chars.append(c)
            elif c in (" ", "_", "-"):
                chars.append(" ")
            # else: drop
        return "".join(chars)
