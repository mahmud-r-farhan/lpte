"""Language-specific data used by the classifier.

Treat a profile as immutable once an engine has been built from it: the engine
compiles lookup indexes at construction time. Build a new engine after changing
vocabulary or rules.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from lpte.core.stemmer import Stemmer

CATEGORIES = frozenset({"profanity", "insult", "sexual", "slur", "threat"})


@dataclass
class LanguageProfile:
    """Vocabulary, morphology and per-term moderation categories for one pack.

    ``context_rules`` maps a bad term to *whole benign words or phrases* that
    contain it, not to words that simply happen to appear elsewhere in a text.
    Uncategorised terms are treated as profanity; tag slurs and threats
    explicitly so the policy can assign the right action.
    """

    language_code: str
    language_name: str
    bad_words: set[str]
    stemmer: Stemmer
    context_rules: dict[str, set[str]] = field(default_factory=dict)
    min_word_length: int = 2
    version: str = "1.0.0"
    description: str = ""
    author: str = ""
    word_categories: dict[str, str] = field(default_factory=dict)
    # Normalized misspellings, romanizations or local slang -> canonical bad term.
    aliases: dict[str, str] = field(default_factory=dict)
    # Optional routing hint for mixed-language engines. If empty, inferred from
    # the vocabulary. Values are Unicode script names (e.g. Latin, Bengali).
    scripts: tuple[str, ...] = ()
