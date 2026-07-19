"""Tests for JSON language pack loader."""

import json
import tempfile
from pathlib import Path

import pytest

from lpte.core.loader import LanguagePackLoader, SuffixStripper


class TestSuffixStripper:
    def test_strips_suffixes(self):
        stemmer = SuffixStripper(["tion", "ness", "ing", "ly", "s"], min_stem_length=3)
        assert stemmer.stem("fucking") == "fuck"
        assert stemmer.stem("slowly") == "slow"
        assert stemmer.stem("fucks") == "fuck"

    def test_short_words_returned_as_is(self):
        stemmer = SuffixStripper(["tion"], min_stem_length=3)
        assert stemmer.stem("as") == "as"

    def test_no_match_returns_word(self):
        stemmer = SuffixStripper(["xyz"], min_stem_length=2)
        assert stemmer.stem("hello") == "hello"


class TestLanguagePackLoader:
    def test_load_json(self):
        data = {
            "language_code": "test",
            "language_name": "Test Language",
            "bad_words": ["bad1", "bad2"],
            "context_rules": {"bad1": ["good1"]},
            "min_word_length": 2,
            "suffix_rules": ["ed", "ing", "s"],
        }
        profile = LanguagePackLoader.load_json(json.dumps(data))

        assert profile.language_code == "test"
        assert profile.language_name == "Test Language"
        assert "bad1" in profile.bad_words
        assert "bad2" in profile.bad_words
        assert profile.context_rules["bad1"] == {"good1"}
        assert profile.min_word_length == 2

    def test_load_file(self):
        data = {
            "language_code": "test",
            "language_name": "Test",
            "bad_words": ["word1"],
        }
        with tempfile.NamedTemporaryFile(mode="w", suffix=".json", delete=False) as f:
            json.dump(data, f)
            f.flush()
            profile = LanguagePackLoader.load_file(f.name)

        assert profile.language_code == "test"
        assert "word1" in profile.bad_words

    def test_stemmer_from_suffix_rules(self):
        data = {
            "language_code": "test",
            "language_name": "Test",
            "bad_words": ["badword"],
            "suffix_rules": ["ing", "ed", "s"],
        }
        profile = LanguagePackLoader.load_json(json.dumps(data))
        assert profile.stemmer.stem("badwording") == "badword"
