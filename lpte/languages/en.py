"""English language pack — stemmer, profile, and dictionary."""

from lpte.core.profile import LanguageProfile
from lpte.core.stemmer import Stemmer


class EnglishStemmer(Stemmer):
    """
    English language stemmer — simplified suffix stripping.

    Handles common inflections:
    - Plurals: -s, -es, -ies
    - Past tense: -ed, -ied
    - Progressive: -ing
    - Comparative: -er, -est
    - Derivational: -tion, -ness, -ment, -able

    Lightweight — prioritizes recall (catching all toxic forms) over precision.
    """

    SUFFIXES = sorted(
        [
            # Long suffixes first
            "ification", "fulness", "ousness", "iveness",
            "ation", "ition", "ness", "ment", "able", "ible",
            "tion", "sion", "ence", "ance",
            # Verb endings
            "ating", "izing", "ifying", "ening",
            "ing", "ied", "ies",
            # Adjective/adverb
            "ful", "less", "ous", "ive", "ial", "ual",
            "ly", "er", "est",
            # Plurals and past
            "sses", "shes", "ches", "xes", "zes",
            "ies", "ves",
            "ed", "es", "s",
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
                stemmed = word[: -len(suffix)]
                # Restore 'y' after dropping 'ied'/'ies'
                if suffix in ("ied", "ies"):
                    return stemmed + "y"
                return stemmed

        return word


# English profanity dictionary — root forms
_ENGLISH_BAD_WORDS: set[str] = {
    # General profanity
    "fuck", "shit", "ass", "asshole", "bastard", "damn",
    "hell", "crap", "piss", "dick", "cock", "pussy", "tits",
    # Slurs — racial/ethnic
    "nigger", "nigga", "spic", "chink", "kike", "wetback",
    "cracker", "honky", "gook", "towelhead",
    # Slurs — gender/sexuality
    "faggot", "fag", "dyke", "homo", "queer",
    "tranny", "shemale",
    # Slurs — disability
    "retard", "retarded", "cripple", "spastic",
    # Severe
    "motherfucker", "cocksucker", "bullshit",
}

EnglishProfile = LanguageProfile(
    language_code="en",
    language_name="English",
    bad_words=_ENGLISH_BAD_WORDS,
    stemmer=EnglishStemmer(),
    context_rules={
        "ass": {"class", "grass", "bass", "brass", "mass", "pass"},
        "hell": {"hello", "shell", "hellen", "helo"},
    },
    min_word_length=2,
)
