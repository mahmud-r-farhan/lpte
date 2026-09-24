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

Performance notes (on-device focus):
- Per-character Unicode category lookups are memoized in a process-level dict —
  real text has a small distinct-character set, so steady-state cost is a dict hit.
- Bulk character mapping (zero-width strip, leet reversal, homoglyphs,
  multilingual sanitization) runs through ``str.translate`` (C-level loop)
  instead of Python-level per-character joins.
- ``normalize_with_alternatives`` computes the shared pre-leet intermediate
  state once and reuses a precomputed primary normalization when the caller
  (e.g. ``LpteEngine``) already has it, avoiding repeated pipeline passes.
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

# Pre-built translate table for leet reversal (C-speed str.translate)
_LEET_TRANS: dict[int, str] = str.maketrans(_LEET_MAP)

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

# Pre-built translate table for homoglyph normalization
_HOMOGLYPH_TRANS: dict[int, str] = str.maketrans(_HOMOGLYPH_MAP)

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
    "\u00A0",  # non-breaking space
})

# Translate table removing all known invisible characters in one C-level pass
_ZERO_WIDTH_TRANS: dict[int, None] = {ord(c): None for c in _ZERO_WIDTH_CHARS}

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

# Sentence-final "!" / "+" are real punctuation, not leetspeak. The leet map
# turns them into letters ("ass!" → "assi", "C++" → "ctt"), which silently
# breaks detection on the extremely common "insult!" chat pattern. This
# pattern isolates the non-interior occurrences so a punctuation-stripped
# variant can be generated (see normalize_with_alternatives).
_TRAILING_LEET_PUNCT_RE = re.compile(r"[!+](?![0-9A-Za-z])")


# ─── Memoized Unicode Helpers ─────────────────────────────────────────────────

# Process-level memoization for unicodedata.category(). Real-world text uses a
# small set of distinct characters, so this converges to pure dict hits.
_CATEGORY_CACHE: dict[str, str] = {}


def _category(c: str) -> str:
    """unicodedata.category with memoization."""
    cat = _CATEGORY_CACHE.get(c)
    if cat is None:
        cat = unicodedata.category(c)
        _CATEGORY_CACHE[c] = cat
    return cat


class _SanitizeMap(dict):
    """
    Translate mapping for multilingual sanitization with memoized misses.

    Keeps letters (L), numbers (N), and combining marks (M) across all scripts;
    every other character maps to a space. Grows lazily — after warm-up each
    character is a single dict hit inside the C-level str.translate loop.
    """

    def __missing__(self, key: int) -> str:  # noqa: D105
        c = chr(key)
        value = c if _category(c)[0] in ("L", "N", "M") else " "
        self[key] = value
        return value


_SANITIZE_MAP = _SanitizeMap()


class TextNormalizer:
    """Normalizes raw text into canonical form for toxicity analysis."""

    def normalize(self, text: str) -> str:
        """
        Run the full normalization pipeline.
        Returns normalized lowercase string.
        """
        return self._post_leet(self._pre_leet(text).translate(_LEET_TRANS))

    def normalize_aggressive(self, text: str, primary: str | None = None) -> str:
        """
        Aggressive normalization — collapses ALL repeated chars to 1.
        Used as a secondary pass when primary normalization doesn't match.

        Args:
            text: Raw input text.
            primary: Already-computed primary normalization to build on.
                     When provided, the pipeline is not re-run.
        """
        base = primary if primary is not None else self.normalize(text)
        return _REPEAT_2PLUS_RE.sub(r"\1", base).strip()

    def normalize_with_alternatives(
        self,
        text: str,
        primary: str | None = None,
    ) -> list[str]:
        """
        Generate multiple normalized variants using alternative leet mappings.
        Returns list of variants to try (primary first, then alternatives).

        Args:
            text: Raw input text.
            primary: Already-computed primary normalization. When provided it
                     is reused as variants[0] instead of being recomputed.
        """
        primary_norm = primary if primary is not None else self.normalize(text)
        variants = [primary_norm]

        # Ambiguous leet chars present in the raw text, in order of appearance
        # (deterministic variant ordering across runs).
        alt_chars: list[str] = []
        seen_alt: set[str] = set()
        for c in text:
            if c in _LEET_ALTERNATIVES and c not in seen_alt:
                seen_alt.add(c)
                alt_chars.append(c)

        if alt_chars or _TRAILING_LEET_PUNCT_RE.search(text):
            # Shared intermediate state: everything before leet reversal.
            pre_leet = self._pre_leet(text)
            # Variant with sentence-final "!"/"+" treated as punctuation, so
            # "you ass!" and "idiot!" resolve to their real forms.
            if _TRAILING_LEET_PUNCT_RE.search(text):
                variant = self._post_leet(
                    _TRAILING_LEET_PUNCT_RE.sub(" ", pre_leet).translate(_LEET_TRANS)
                )
                if variant and variant not in variants:
                    variants.append(variant)
            for alt_char in alt_chars:
                for alt in _LEET_ALTERNATIVES[alt_char]:
                    trans = dict(_LEET_TRANS)
                    trans[ord(alt_char)] = alt
                    variant = self._post_leet(pre_leet.translate(trans))
                    if variant and variant not in variants:
                        variants.append(variant)

        # Also add aggressive collapse variant (built on the primary — no re-run)
        aggressive = self.normalize_aggressive(text, primary=primary_norm)
        if aggressive and aggressive not in variants:
            variants.append(aggressive)

        return variants

    # ─── Pipeline Stages ──────────────────────────────────────────────────────

    def _pre_leet(self, text: str) -> str:
        """Stages before leet reversal: invisibles, homoglyphs, accents, NFC."""
        result = self._strip_zero_width(text)
        result = self._apply_homoglyphs(result)
        result = _LATIN_ACCENT_RE.sub("", result)
        return unicodedata.normalize("NFC", result)

    def _post_leet(self, result: str) -> str:
        """Stages after leet reversal: separators, repeats, sanitize, fold."""
        result = self._strip_separators(result)
        result = _REPEAT_3PLUS_RE.sub(r"\1\1", result)
        result = result.translate(_SANITIZE_MAP)
        result = result.lower()
        return " ".join(result.split()).strip()

    # ─── Private Helpers ──────────────────────────────────────────────────────

    def _strip_zero_width(self, text: str) -> str:
        """
        Strip known invisible chars + Unicode Cf (format) category.

        Fast paths: pure-ASCII text never contains invisibles; otherwise a
        single C-level translate removes the known set, and the category scan
        only runs when a distinct character is actually in category Cf.
        """
        if text.isascii():
            return text
        result = text.translate(_ZERO_WIDTH_TRANS)
        if not result:
            return result
        # Scan distinct characters (memoized) for unknown Cf chars
        has_cf = False
        for c in set(result):
            if _category(c) == _FORMAT_CATEGORY:
                has_cf = True
                break
        if not has_cf:
            return result
        return "".join(c for c in result if _category(c) != _FORMAT_CATEGORY)

    def _apply_homoglyphs(self, text: str) -> str:
        """
        Apply homoglyph mappings to words that mix Latin letters with lookalikes
        (e.g., 'fаck' with Cyrillic 'а'). Avoids altering pure Cyrillic/Greek text.
        """
        # Fast path: pure ASCII text cannot contain non-ASCII homoglyphs.
        # This skips a per-word, per-character scan on the common case.
        if text.isascii():
            return text
        words = text.split()
        normalized_words = []
        for w in words:
            # Check if word has Latin characters alongside lookalikes
            if w.isascii():
                normalized_words.append(w)
                continue
            has_latin = any("a" <= c.lower() <= "z" for c in w)
            has_fullwidth = any(0xFF00 <= ord(c) <= 0xFFEF for c in w)
            if has_latin or has_fullwidth:
                w = w.translate(_HOMOGLYPH_TRANS)
            normalized_words.append(w)
        return " ".join(normalized_words)

    def _apply_leet_reversal(self, text: str) -> str:
        return text.translate(_LEET_TRANS)

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
        return text.translate(_SANITIZE_MAP)
