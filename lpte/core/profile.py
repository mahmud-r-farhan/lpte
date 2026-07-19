"""
Language profile interface.

Each language provides:
- A set of known profanity root words
- A stemmer for suffix stripping
- Optional context rules for ambiguity resolution
"""

from __future__ import annotations

from dataclasses import dataclass, field

from lpte.core.stemmer import Stemmer


@dataclass
class LanguageProfile:
    """
    Language-specific configuration for toxicity detection.

    To add a new language, create a LanguageProfile with:
    1. language_code: ISO 639-1 code
    2. bad_words: set of known profanity root forms
    3. stemmer: language-specific Stemmer implementation
    4. Optional context_rules for disambiguation
    """

    language_code: str
    language_name: str
    bad_words: set[str]
    stemmer: Stemmer
    context_rules: dict[str, set[str]] = field(default_factory=dict)
    min_word_length: int = 2
