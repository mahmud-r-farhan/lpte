"""French language pack — stemmer, profile, and dictionary."""

from lpte.core.profile import LanguageProfile
from lpte.core.stemmer import Stemmer


class FrenchStemmer(Stemmer):
    """
    French language stemmer — suffix stripping for verbs, nouns, adjectives.
    """

    SUFFIXES = sorted(
        [
            # Adverb and noun suffixes
            "issements", "issement", "abilites", "abilite", "ateurs", "ateur",
            "atrices", "atrice", "ations", "ation", "ements", "ement",
            "euses", "euse", "ismes", "isme", "istes", "iste",
            "eaux", "esses", "esse", "eaux",
            # Verb endings
            "assent", "assiez", "assions", "erions", "eriez", "erons", "erez",
            "aient", "antes", "ante", "ants", "ant",
            "asses", "asse", "erais", "erait", "eront",
            "ions", "iez", "ent", "era", "er", "es", "ez", "ai", "as", "a",
            # Plurals and feminine forms
            "euses", "eux", "elles", "elle", "s", "e",
        ],
        key=len,
        reverse=True,
    )

    MIN_STEM_LENGTH = 3

    def stem(self, word: str) -> str:
        if len(word) < self.MIN_STEM_LENGTH + 2:
            return word

        for suffix in self.SUFFIXES:
            if word.endswith(suffix) and len(word) - len(suffix) >= self.MIN_STEM_LENGTH:
                return word[: -len(suffix)]

        return word


_FRENCH_BAD_WORDS: set[str] = {
    # General profanity
    "merde", "merdeux", "merdeuse", "putain", "pute", "putes",
    "salope", "salopes", "salaud", "salauds", "connard", "connards",
    "connasse", "connasses", "conne", "connes", "con", "cons",
    "encule", "enculer", "encules", "enculee",
    "batard", "batarde", "batards", "batardes",
    "chier", "chie", "chieur", "chieuse",
    "bordel", "foutre", "foutu", "foutue",
    "nique", "niquer", "niquez", "niquee",
    "bite", "bites", "couille", "couilles", "cul", "fesses",
    # Slurs
    "pd", "pede", "pedale", "tapette", "gouine",
    "bougnoule", "negre", "bicot", "raton",
    "debile", "abriti", "idiot", "idiote", "creve",
    "gueule", "ta gueule", "ferme ta gueule",
}

# ─── Content Categories ───────────────────────────────────────────────────────
# Slurs and threats escalate severity; profanity is the default.
_FRENCH_WORD_CATEGORIES: dict[str, str] = {
    **{w: "threat" for w in (
        "creve",
    )},
    **{w: "slur" for w in (
        "negre", "bougnoule", "bicot", "raton", "pd", "pede",
        "pedale", "tapette", "gouine", "salope", "salopes", "salaud",
        "salauds", "pute", "putes", "connasse", "connasses", "encule",
        "encules", "enculee", "enculer",
    )},
    **{w: "sexual" for w in (
        "bite", "bites", "couille", "couilles", "cul", "fesses",
        "nique", "niquer", "niquez", "niquee", "chier", "chie",
        "chieur", "chieuse",
    )},
    **{w: "insult" for w in (
        "connard", "connards", "conne", "connes", "con", "cons",
        "debile", "abriti", "idiot", "idiote", "batard", "batarde",
        "batards", "batardes",
    )},
}

FrenchProfile = LanguageProfile(
    language_code="fr",
    language_name="Français (French)",
    bad_words=_FRENCH_BAD_WORDS,
    stemmer=FrenchStemmer(),
    word_categories=_FRENCH_WORD_CATEGORIES,
    context_rules={},
    min_word_length=2,
    version="1.1.0",
    description="French profanity and toxicity word list with stemmer",
    author="LPTE Contributors",
)
