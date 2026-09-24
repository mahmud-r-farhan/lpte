"""
Centralized Language Registry.

Provides thread-safe dynamic language pack registration, lookup, persistence,
and schema metadata for dynamic form generators.
"""

from __future__ import annotations

import json
import threading
from pathlib import Path
from typing import Any

from lpte.core.loader import LanguagePackLoader
from lpte.core.profile import LanguageProfile

_KNOWN_CATEGORIES = ["profanity", "insult", "sexual", "slur", "threat"]


class LanguageRegistry:
    """
    Thread-safe registry for managing language profiles dynamically.
    """

    def __init__(self, languages_dir: str | Path | None = None):
        self._lock = threading.RLock()
        self._profiles: dict[str, LanguageProfile] = {}
        self._persisted_sources: dict[str, Path] = {}

        if languages_dir is not None:
            self._languages_dir = Path(languages_dir)
        else:
            # Fallback to local ./languages or package languages
            cwd_langs = Path.cwd() / "languages"
            pkg_langs = Path(__file__).parent.parent.parent / "languages"
            self._languages_dir = cwd_langs if cwd_langs.is_dir() else pkg_langs

        # Load default built-in profiles and JSON packs
        self._load_builtins()
        self._load_dir_packs()

    @property
    def languages_dir(self) -> Path:
        return self._languages_dir

    def _load_builtins(self) -> None:
        """Load built-in Python language profiles."""
        try:
            from lpte.languages import (
                ArabicProfile, BengaliProfile, ChineseProfile, EnglishProfile,
                FrenchProfile, GermanProfile, HindiProfile, JapaneseProfile,
                KoreanProfile, RussianProfile, SpanishProfile,
            )
            builtins = [
                EnglishProfile, BengaliProfile, ChineseProfile, JapaneseProfile,
                KoreanProfile, RussianProfile, SpanishProfile, HindiProfile,
                FrenchProfile, GermanProfile, ArabicProfile,
            ]
            with self._lock:
                for p in builtins:
                    self._profiles[p.language_code.lower()] = p
        except Exception:
            pass

    def _load_dir_packs(self) -> None:
        """Scan directory for *_profile.json files."""
        dirs_to_check = [self._languages_dir, Path.cwd() / "languages"]
        for d in dirs_to_check:
            if d.is_dir():
                try:
                    for path in sorted(d.glob("*_profile.json")):
                        try:
                            prof = LanguagePackLoader.load_file(path)
                            code = prof.language_code.lower()
                            with self._lock:
                                self._profiles[code] = prof
                                self._persisted_sources[code] = path
                        except Exception:
                            pass
                except Exception:
                    pass

    def register_profile(
        self,
        profile: LanguageProfile,
        persist: bool = False,
        custom_dir: str | Path | None = None,
        raw_dict: dict[str, Any] | None = None,
    ) -> LanguageProfile:
        """
        Register a LanguageProfile in memory and optionally persist to disk.
        """
        code = profile.language_code.lower().strip()
        if not code:
            raise ValueError("Language code cannot be empty")

        with self._lock:
            self._profiles[code] = profile

            if persist:
                target_dir = Path(custom_dir) if custom_dir else self._languages_dir
                target_dir.mkdir(parents=True, exist_ok=True)
                file_path = target_dir / f"{code}_profile.json"

                if raw_dict is None:
                    raw_dict = self.to_dict(profile)

                with open(file_path, "w", encoding="utf-8") as f:
                    json.dump(raw_dict, f, ensure_ascii=False, indent=2)

                self._persisted_sources[code] = file_path

        return profile

    def register_dict(
        self,
        data: dict[str, Any],
        persist: bool = False,
        custom_dir: str | Path | None = None,
    ) -> LanguageProfile:
        """Register a language pack from a dictionary."""
        profile = LanguagePackLoader.load_dict(data)
        return self.register_profile(profile, persist=persist, custom_dir=custom_dir, raw_dict=data)

    def register_json(
        self,
        json_str: str,
        persist: bool = False,
        custom_dir: str | Path | None = None,
    ) -> LanguageProfile:
        """Register a language pack from a JSON string."""
        profile = LanguagePackLoader.load_json(json_str)
        try:
            raw_dict = json.loads(json_str)
        except Exception:
            raw_dict = None
        return self.register_profile(profile, persist=persist, custom_dir=custom_dir, raw_dict=raw_dict)

    def register_file(
        self,
        file_path: str | Path,
        persist: bool = False,
    ) -> LanguageProfile:
        """Register a language pack from a JSON file path."""
        path = Path(file_path)
        profile = LanguagePackLoader.load_file(path)
        with open(path, "r", encoding="utf-8") as f:
            raw_dict = json.load(f)
        return self.register_profile(profile, persist=persist, raw_dict=raw_dict)

    def get_profile(self, code: str) -> LanguageProfile | None:
        """Look up a registered profile by language code."""
        with self._lock:
            return self._profiles.get(code.lower().strip())

    def get_all_profiles(self) -> dict[str, LanguageProfile]:
        """Return a copy of all registered profiles."""
        with self._lock:
            return dict(self._profiles)

    def remove_profile(self, code: str, delete_file: bool = False) -> bool:
        """
        Unregister a language code and optionally delete its persisted JSON pack.
        """
        code = code.lower().strip()
        with self._lock:
            if code not in self._profiles:
                return False

            del self._profiles[code]

            if delete_file and code in self._persisted_sources:
                file_path = self._persisted_sources.pop(code)
                if file_path.exists():
                    try:
                        file_path.unlink()
                    except OSError:
                        pass
            return True

    def to_dict(self, profile: LanguageProfile) -> dict[str, Any]:
        """Export a LanguageProfile back into a standard language pack dictionary."""
        suffixes = getattr(profile.stemmer, "suffixes", [])
        context_rules = {k: list(v) for k, v in profile.context_rules.items()}
        return {
            "language_code": profile.language_code,
            "language_name": profile.language_name,
            "bad_words": sorted(profile.bad_words),
            "suffix_rules": sorted(suffixes) if suffixes else [],
            "context_rules": context_rules,
            "word_categories": dict(profile.word_categories),
            "min_word_length": profile.min_word_length,
            "version": profile.version,
            "description": profile.description,
            "author": profile.author,
        }

    def export_json(self, code: str) -> str:
        """Export a registered profile as formatted JSON."""
        prof = self.get_profile(code)
        if not prof:
            raise ValueError(f"Unknown language code '{code}'")
        return json.dumps(self.to_dict(prof), ensure_ascii=False, indent=2)

    @staticmethod
    def get_schema() -> dict[str, Any]:
        """
        Returns JSON schema and metadata for dynamic language forms.
        Used by frontends / external tools to automatically generate forms.
        """
        return {
            "$schema": "https://json-schema.org/draft/2020-12/schema",
            "title": "LPTE Language Pack Schema",
            "type": "object",
            "required": ["language_code", "language_name", "bad_words"],
            "categories": _KNOWN_CATEGORIES,
            "properties": {
                "language_code": {
                    "type": "string",
                    "title": "Language Code",
                    "description": "ISO 639-1 language code (e.g. 'it', 'pt', 'bn')",
                    "examples": ["it", "pt", "tr", "vi"],
                    "minLength": 2,
                    "maxLength": 10,
                },
                "language_name": {
                    "type": "string",
                    "title": "Language Name",
                    "description": "Human-readable native/English name (e.g. 'Italiano')",
                    "examples": ["Italiano", "Português", "Türkçe"],
                },
                "bad_words": {
                    "type": "array",
                    "title": "Toxic / Profane Word List",
                    "description": "List of toxic root words, slurs, or phrases.",
                    "items": {"type": "string"},
                    "minItems": 1,
                },
                "suffix_rules": {
                    "type": "array",
                    "title": "Suffix Stemming Rules",
                    "description": "Known inflections/suffixes to strip during normalization.",
                    "items": {"type": "string"},
                    "default": [],
                },
                "word_categories": {
                    "type": "object",
                    "title": "Word Categories",
                    "description": "Map bad word -> content harm category ('profanity', 'insult', 'sexual', 'slur', 'threat').",
                    "additionalProperties": {
                        "type": "string",
                        "enum": _KNOWN_CATEGORIES,
                    },
                    "default": {},
                },
                "context_rules": {
                    "type": "object",
                    "title": "Context Rules (Disambiguation)",
                    "description": "Map bad word -> list of safe benign compound words.",
                    "additionalProperties": {
                        "type": "array",
                        "items": {"type": "string"},
                    },
                    "default": {},
                },
                "min_word_length": {
                    "type": "integer",
                    "title": "Minimum Word Length",
                    "description": "Minimum length of tokens to evaluate (default: 2).",
                    "default": 2,
                    "minimum": 1,
                },
                "version": {
                    "type": "string",
                    "title": "Pack Version",
                    "default": "1.0.0",
                },
                "description": {
                    "type": "string",
                    "title": "Description",
                    "default": "",
                },
                "author": {
                    "type": "string",
                    "title": "Author / Contributor",
                    "default": "",
                },
            },
        }


# Global default instance
default_registry = LanguageRegistry()
