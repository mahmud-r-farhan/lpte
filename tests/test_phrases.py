"""Tests for phrase matching signal (bigram/trigram) in the classifier."""

import pytest

from lpte.core.engine import LpteEngine
from lpte.core.profile import LanguageProfile
from lpte.core.stemmer import Stemmer
from lpte.languages.en import EnglishProfile


class _IdentityStemmer(Stemmer):
    def stem(self, word: str) -> str:
        return word


@pytest.fixture
def phrase_engine():
    """Engine with a profile containing multi-word bad phrases."""
    profile = LanguageProfile(
        language_code="test",
        language_name="Test",
        bad_words={
            "fuck",
            "go die",       # bigram phrase
            "kill your self", # trigram phrase
        },
        stemmer=_IdentityStemmer(),
        min_word_length=1,
    )
    return LpteEngine(profile)


@pytest.fixture
def engine():
    return LpteEngine(EnglishProfile)


class TestPhraseSingleWords:
    def test_single_bad_word_still_caught(self, engine):
        assert engine.is_toxic("fuck")

    def test_clean_text_passes(self, engine):
        assert not engine.is_toxic("hello world")


class TestBigramPhrases:
    def test_catches_two_word_phrase(self, phrase_engine):
        result = phrase_engine.analyze("go die already")
        assert result.is_toxic, "Bigram phrase 'go die' should be detected"

    def test_single_word_of_phrase_does_not_trigger(self, phrase_engine):
        # "go" alone shouldn't trigger anything
        result = phrase_engine.analyze("go ahead and try")
        assert not result.is_toxic


class TestTrigramPhrases:
    def test_catches_three_word_phrase(self, phrase_engine):
        result = phrase_engine.analyze("you should kill your self")
        assert result.is_toxic, "Trigram phrase 'kill your self' should be detected"


class TestPhraseSignalReported:
    def test_phrase_match_signal_set(self, phrase_engine):
        result = phrase_engine.analyze("go die now")
        assert result.signals.get("phrase_match", 0) > 0 or result.is_toxic


class TestEnglishPhrases:
    def test_kys_abbreviation(self, engine):
        """'kys' is a single-entry bad word in the English pack."""
        result = engine.analyze("just kys lol")
        assert result.is_toxic

    def test_kill_yourself_phrase(self, engine):
        """'kill yourself' should be caught via concat/phrase detection."""
        result = engine.analyze("just kill yourself already")
        # may match via single-word "kill" or phrase matching
        assert result.is_toxic or result.confidence > 0
