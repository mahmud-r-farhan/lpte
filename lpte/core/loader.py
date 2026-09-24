"""Validated, zero-dependency JSON language-pack loading.

A JSON pack can define vocabulary, benign compounds, categories, suffix rules
and optional Unicode script routing without adding Python code. All errors
include the source/field so a bad pack fails validation before deployment.
"""

from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any

from lpte.core.normalizer import TextNormalizer
from lpte.core.profile import CATEGORIES, LanguageProfile
from lpte.core.stemmer import Stemmer

_REQUIRED = ("language_code", "language_name", "bad_words")
_ALLOWED = frozenset(
    {
        *_REQUIRED,
        "context_rules",
        "word_categories",
        "aliases",
        "min_word_length",
        "suffix_rules",
        "scripts",
        "version",
        "description",
        "author",
    }
)
_SCRIPTS = frozenset(
    {
        "Latin",
        "Cyrillic",
        "Bengali",
        "Devanagari",
        "Arabic",
        "Han",
        "Kana",
        "Hangul",
        "Greek",
        "Other",
    }
)
_CODE_RE = re.compile(r"^[a-z]{2,8}(?:-[a-z]{2,8})?$")


def _strings(value: Any, name: str, source: str, *, nonempty: bool = False) -> list[str]:
    if not isinstance(value, list) or (nonempty and not value):
        raise ValueError(
            f"{source}: '{name}' must be a {'non-empty ' if nonempty else ''}list of strings"
        )
    if any(not isinstance(s, str) or not s.strip() or s != s.strip() for s in value):
        raise ValueError(f"{source}: '{name}' entries must be non-empty, trimmed strings")
    if len(value) != len(set(value)):
        raise ValueError(f"{source}: '{name}' contains duplicate entries")
    return value


def _validate_pack(data: Any, source: str) -> dict[str, Any]:
    if not isinstance(data, dict):
        raise ValueError(f"{source}: language pack must be a JSON object")
    if any(not isinstance(key, str) for key in data):
        raise ValueError(f"{source}: language pack keys must be strings")
    missing = set(_REQUIRED) - data.keys()
    if missing:
        raise ValueError(f"{source}: missing required fields: {', '.join(sorted(missing))}")
    unknown = data.keys() - _ALLOWED
    if unknown:
        raise ValueError(f"{source}: unknown field(s): {', '.join(sorted(unknown))}")
    code = data["language_code"]
    if not isinstance(code, str) or not _CODE_RE.fullmatch(code):
        raise ValueError(
            f"{source}: 'language_code' must be a lowercase language code (e.g. 'ur' or 'bn-latn')"
        )
    for key in ("language_name", "version", "description", "author"):
        if key in data and (
            not isinstance(data[key], str) or (key == "language_name" and not data[key].strip())
        ):
            raise ValueError(f"{source}: '{key}' must be a string")
    words = _strings(data["bad_words"], "bad_words", source, nonempty=True)
    normalizer = TextNormalizer()

    def canonical(term: str, field_name: str) -> None:
        normalized = normalizer.normalize(term)
        if normalized != term:
            raise ValueError(
                f"{source}: '{field_name}' term {term!r} is not normalized; use {normalized!r}"
            )

    for term in words:
        canonical(term, "bad_words")
    word_set = set(words)
    min_len = data.get("min_word_length", 2)
    if type(min_len) is not int or min_len < 1:
        raise ValueError(f"{source}: 'min_word_length' must be a positive integer")
    _strings(data.get("suffix_rules", []), "suffix_rules", source)
    scripts = _strings(data.get("scripts", []), "scripts", source)
    if set(scripts) - _SCRIPTS:
        raise ValueError(f"{source}: unknown scripts: {', '.join(sorted(set(scripts) - _SCRIPTS))}")

    aliases = data.get("aliases", {})
    if not isinstance(aliases, dict):
        raise ValueError(f"{source}: 'aliases' must be an object mapping variants to bad words")
    for variant, target in aliases.items():
        if not isinstance(variant, str) or not variant.strip() or variant != variant.strip():
            raise ValueError(f"{source}: alias keys must be non-empty, trimmed strings")
        if not isinstance(target, str) or target not in word_set:
            raise ValueError(f"{source}: alias '{variant}' must refer to a term in bad_words")
        canonical(variant, "aliases")
        if variant in word_set:
            raise ValueError(f"{source}: alias '{variant}' is already in bad_words")
    for key in ("context_rules", "word_categories"):
        mapping = data.get(key, {})
        if not isinstance(mapping, dict):
            raise ValueError(f"{source}: '{key}' must be an object keyed by bad word")
        invalid = sorted(set(mapping) - word_set)
        if invalid:
            raise ValueError(f"{source}: '{key}' contains terms not in bad_words: {invalid}")
        for term, value in mapping.items():
            if key == "context_rules":
                for phrase in _strings(value, f"context_rules.{term}", source):
                    canonical(phrase, f"context_rules.{term}")
            elif not isinstance(value, str) or value not in CATEGORIES:
                allowed = ", ".join(sorted(CATEGORIES))
                raise ValueError(f"{source}: 'word_categories.{term}' must be one of {allowed}")
    return data


class SuffixStripper(Stemmer):
    """Generic indexed, longest-suffix-first stemmer for data-only packs."""

    def __init__(self, suffixes: list[str], min_stem_length: int = 2):
        self.suffixes = sorted(suffixes, key=len, reverse=True)
        self.min_stem_length = min_stem_length
        buckets: dict[str, list[str]] = {}
        for suffix in self.suffixes:
            buckets.setdefault(suffix[-1], []).append(suffix)
        self._buckets = buckets

    def stem(self, word: str) -> str:
        if len(word) < self.min_stem_length + 1:
            return word
        for suffix in self._buckets.get(word[-1], ()):
            if word.endswith(suffix) and len(word) - len(suffix) >= self.min_stem_length:
                return word[: -len(suffix)]
        return word


class _IdentityStemmer(Stemmer):
    def stem(self, word: str) -> str:
        return word


class LanguagePackLoader:
    """Load one JSON pack or an entire directory of ``*_profile.json`` files."""

    @staticmethod
    def load_file(path: str | Path, stemmer: Stemmer | None = None) -> LanguageProfile:
        path = Path(path)
        with path.open(encoding="utf-8") as f:
            try:
                data = json.load(f)
            except json.JSONDecodeError as exc:
                raise ValueError(f"{path}: invalid JSON: {exc}") from exc
        return LanguagePackLoader._from_dict(data, stemmer, str(path))

    @staticmethod
    def load_json(json_str: str, stemmer: Stemmer | None = None) -> LanguageProfile:
        try:
            data = json.loads(json_str)
        except json.JSONDecodeError as exc:
            raise ValueError(f"<json>: invalid JSON: {exc}") from exc
        return LanguagePackLoader._from_dict(data, stemmer, "<json>")

    @staticmethod
    def load_dict(data: dict[str, Any], stemmer: Stemmer | None = None) -> LanguageProfile:
        return LanguagePackLoader._from_dict(data, stemmer, "<dict>")

    @staticmethod
    def load_directory(directory: str | Path) -> dict[str, LanguageProfile]:
        directory = Path(directory)
        if not directory.is_dir():
            raise NotADirectoryError(f"Not a directory: {directory}")
        profiles: dict[str, LanguageProfile] = {}
        for file in sorted(directory.glob("*_profile.json")):
            profile = LanguagePackLoader.load_file(file)
            if file.stem != f"{profile.language_code}_profile":
                raise ValueError(f"{file}: filename must be {profile.language_code}_profile.json")
            if profile.language_code in profiles:
                raise ValueError(f"{file}: duplicate language code '{profile.language_code}'")
            profiles[profile.language_code] = profile
        return profiles

    @staticmethod
    def _from_dict(data: Any, stemmer: Stemmer | None, source: str) -> LanguageProfile:
        data = _validate_pack(data, source)
        if stemmer is None:
            suffixes = data.get("suffix_rules", [])
            stemmer = SuffixStripper(suffixes) if suffixes else _IdentityStemmer()
        return LanguageProfile(
            language_code=data["language_code"],
            language_name=data["language_name"],
            bad_words=set(data["bad_words"]),
            stemmer=stemmer,
            context_rules={k: set(v) for k, v in data.get("context_rules", {}).items()},
            word_categories=dict(data.get("word_categories", {})),
            aliases=dict(data.get("aliases", {})),
            scripts=tuple(data.get("scripts", ())),
            min_word_length=data.get("min_word_length", 2),
            version=data.get("version", "1.0.0"),
            description=data.get("description", ""),
            author=data.get("author", ""),
        )
