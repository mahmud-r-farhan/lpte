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
    "suffix_rules": ["টা", "টি", "রা"],
    "version": "1.0.0",
    "description": "Optional description",
    "author": "Optional author"
}
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from lpte.core.profile import LanguageProfile
from lpte.core.stemmer import Stemmer


# ─── Validation ───────────────────────────────────────────────────────────────

_REQUIRED_FIELDS = ("language_code", "language_name", "bad_words")


def _validate_pack(data: dict[str, Any], source: str = "<unknown>") -> None:
    """Validate a language pack dict. Raises ValueError with helpful messages."""
    missing = [f for f in _REQUIRED_FIELDS if f not in data]
    if missing:
        raise ValueError(
            f"Language pack '{source}' is missing required fields: {missing}. "
            f"Required: {list(_REQUIRED_FIELDS)}"
        )

    if not isinstance(data["bad_words"], list):
        raise ValueError(
            f"Language pack '{source}': 'bad_words' must be a list of strings, "
            f"got {type(data['bad_words']).__name__}"
        )

    if len(data["bad_words"]) == 0:
        raise ValueError(
            f"Language pack '{source}': 'bad_words' must contain at least one entry"
        )

    if not isinstance(data["language_code"], str) or not data["language_code"].strip():
        raise ValueError(
            f"Language pack '{source}': 'language_code' must be a non-empty string"
        )

    if "context_rules" in data and not isinstance(data["context_rules"], dict):
        raise ValueError(
            f"Language pack '{source}': 'context_rules' must be a dict, "
            f"got {type(data['context_rules']).__name__}"
        )

    if "word_categories" in data and not isinstance(data["word_categories"], dict):
        raise ValueError(
            f"Language pack '{source}': 'word_categories' must be a dict, "
            f"got {type(data['word_categories']).__name__}"
        )

    if "min_word_length" in data:
        mwl = data["min_word_length"]
        if not isinstance(mwl, int) or mwl < 1:
            raise ValueError(
                f"Language pack '{source}': 'min_word_length' must be a positive int, got {mwl!r}"
            )


# ─── SuffixStripper ───────────────────────────────────────────────────────────

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


class _IdentityStemmer(Stemmer):
    """No-op stemmer — returns words unchanged."""

    def stem(self, word: str) -> str:
        return word


# ─── Loader ───────────────────────────────────────────────────────────────────

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

        Raises:
            FileNotFoundError: If path does not exist.
            ValueError: If JSON is missing required fields or has invalid values.
        """
        path = Path(path)
        if not path.exists():
            raise FileNotFoundError(f"Language pack file not found: {path}")

        with open(path, "r", encoding="utf-8") as f:
            data = json.load(f)

        return LanguagePackLoader._from_dict(data, stemmer, source=str(path))

    @staticmethod
    def load_json(json_str: str, stemmer: Stemmer | None = None) -> LanguageProfile:
        """
        Load a language pack from a JSON string.

        Args:
            json_str: JSON string containing language pack data.
            stemmer: Custom stemmer. If None, uses suffix-based stripping.

        Returns:
            Configured LanguageProfile.

        Raises:
            ValueError: If JSON is invalid or missing required fields.
        """
        try:
            data = json.loads(json_str)
        except json.JSONDecodeError as e:
            raise ValueError(f"Invalid JSON string: {e}") from e

        return LanguagePackLoader._from_dict(data, stemmer, source="<json_string>")

    @staticmethod
    def load_dict(data: dict[str, Any], stemmer: Stemmer | None = None) -> LanguageProfile:
        """
        Load a language pack from an already-parsed dict.

        Args:
            data: Dict matching the language pack schema.
            stemmer: Custom stemmer override.

        Returns:
            Configured LanguageProfile.
        """
        return LanguagePackLoader._from_dict(data, stemmer, source="<dict>")

    @staticmethod
    def load_directory(directory: str | Path) -> dict[str, LanguageProfile]:
        """
        Load all ``*_profile.json`` files from a directory.

        Args:
            directory: Directory path to scan.

        Returns:
            Dict mapping ``language_code`` → ``LanguageProfile``.

        Raises:
            NotADirectoryError: If path is not a directory.
        """
        directory = Path(directory)
        if not directory.is_dir():
            raise NotADirectoryError(f"Not a directory: {directory}")

        profiles: dict[str, LanguageProfile] = {}
        for json_file in sorted(directory.glob("*_profile.json")):
            profile = LanguagePackLoader.load_file(json_file)
            profiles[profile.language_code] = profile

        return profiles

    @staticmethod
    def _from_dict(
        data: dict[str, Any],
        stemmer: Stemmer | None = None,
        source: str = "<unknown>",
    ) -> LanguageProfile:
        _validate_pack(data, source)

        suffixes = data.get("suffix_rules", [])

        if stemmer is None:
            if suffixes:
                stemmer = SuffixStripper(suffixes)
            else:
                stemmer = _IdentityStemmer()

        context_rules = {
            k: set(v) for k, v in data.get("context_rules", {}).items()
        }

        word_categories = {
            str(k): str(v) for k, v in data.get("word_categories", {}).items()
        }

        return LanguageProfile(
            language_code=data["language_code"],
            language_name=data["language_name"],
            bad_words=set(data["bad_words"]),
            stemmer=stemmer,
            context_rules=context_rules,
            min_word_length=data.get("min_word_length", 2),
            word_categories=word_categories,
            version=data.get("version", "1.0.0"),
            description=data.get("description", ""),
            author=data.get("author", ""),
        )
