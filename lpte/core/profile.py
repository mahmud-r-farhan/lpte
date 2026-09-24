"""
Language profile interface.

Each language provides:
- A set of known profanity root words
- A stemmer for suffix stripping
- Optional context rules for ambiguity resolution
- Optional metadata (version, description, author)
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
    5. Optional metadata fields: version, description, author
    """

    language_code: str
    language_name: str
    bad_words: set[str]
    stemmer: Stemmer
    context_rules: dict[str, set[str]] = field(default_factory=dict)
    min_word_length: int = 2
    # Optional content-category mapping: bad word → category.
    # Known categories: "profanity" (default when absent), "slur",
    # "threat", "sexual". Slur/threat matches escalate severity by one
    # level and can drive per-category moderation policy thresholds.
    word_categories: dict[str, str] = field(default_factory=dict)
    # Optional: matched phrase → set of benign *object* words.
    #
    # Threat phrases are only threats when the target is a person. "I will
    # kill you" is a threat; "I will kill the process" is a sysadmin. This
    # map says which objects make a matched phrase ordinary speech: when
    # every occurrence of the phrase is directly followed by one of these
    # words (ignoring articles and determiners), the match is suppressed.
    #
    # Deliberately narrow and explicit — it is an allowlist of inanimate
    # objects, not a guess about intent. Anything not listed still flags,
    # which keeps the failure mode on the side of detection.
    benign_objects: dict[str, set[str]] = field(default_factory=dict)
    # Optional metadata
    version: str = "1.0.0"
    description: str = ""
    author: str = ""
