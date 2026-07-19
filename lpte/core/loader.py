"""
JSON-based language pack loader.

Allows adding new languages by dropping a single JSON file — no code changes needed.

JSON format:
{
    "language_code": "bn",
    "language_name": "বাংলা",
    "bad_words": ["word1", "word2"],
    "context_rules": {"word1": ["negator1"]},
    "min_word_length": 2,
    "suffix_rules": ["টা", "টি", "রা"]
}
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from lpte.core.profile import LanguageProfile
from lpte.core.stemmer import Stemmer


class SuffixStripper(Stemmer):
    """Generic stemmer that strips a list of known suffixes."""

    def __init__(self, suffixes: list[str], min_stem_length: int = 2):
        # Sort by length descending for greedy matching
        self.suffixes = sorted(suffixes, key=len, reverse=True)
        self.min_stem_length = min_stem_length

    def stem(self, word: str) -> str:
        if len(word) < self.min_stem_length + 2:
            return word

        for suffix in self.suffixes:
            if word.endswith(suffix) and len(word) - len(suffix) >= self.min_stem_length:
                return word[: -len(suffix)]

        return word


class LanguagePackLoader:
    """Load language profiles from JSON data files."""

    @staticmethod
    def load_file(path: str | Path, stemmer: Stemmer | None = None) -> LanguageProfile:
        """
        Load a language pack from a JSON file.

        Args:
            path: Path to JSON language pack file.
            stemmer: Custom stemmer. If None, uses suffix-based stripping
                     from the "suffix_rules" field in the JSON.

        Returns:
            Configured LanguageProfile.
        """
        with open(path, "r", encoding="utf-8") as f:
            data = json.load(f)
        return LanguagePackLoader._from_dict(data, stemmer)

    @staticmethod
    def load_json(json_str: str, stemmer: Stemmer | None = None) -> LanguageProfile:
        """
        Load a language pack from a JSON string.

        Args:
            json_str: JSON string containing language pack data.
            stemmer: Custom stemmer. If None, uses suffix-based stripping.

        Returns:
            Configured LanguageProfile.
        """
        data = json.loads(json_str)
        return LanguagePackLoader._from_dict(data, stemmer)

    @staticmethod
    def _from_dict(data: dict[str, Any], stemmer: Stemmer | None = None) -> LanguageProfile:
        suffixes = data.get("suffix_rules", [])

        if stemmer is None:
            if suffixes:
                stemmer = SuffixStripper(suffixes)
            else:
                # Fallback: identity stemmer (no-op)
                stemmer = _IdentityStemmer()

        context_rules = {
            k: set(v) for k, v in data.get("context_rules", {}).items()
        }

        return LanguageProfile(
            language_code=data["language_code"],
            language_name=data["language_name"],
            bad_words=set(data["bad_words"]),
            stemmer=stemmer,
            context_rules=context_rules,
            min_word_length=data.get("min_word_length", 2),
        )


class _IdentityStemmer(Stemmer):
    """No-op stemmer — returns words unchanged."""

    def stem(self, word: str) -> str:
        return word
