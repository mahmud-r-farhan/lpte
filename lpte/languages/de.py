"""German language pack — stemmer, profile, and dictionary."""

from lpte.core.profile import LanguageProfile
from lpte.core.stemmer import Stemmer


class GermanStemmer(Stemmer):
    """
    German language stemmer — strips common German inflectional suffixes.
    """

    SUFFIXES = sorted(
        [
            # Complex noun / adj suffixes
            "keit", "heit", "ung", "schaft", "isch", "lich", "ig",
            # Verb / adjective / noun inflections
            "enden", "endem", "ender", "endes", "ende",
            "test", "ten", "tet", "tem", "ter", "tes",
            "est", "ern", "erm", "ers", "eln",
            "en", "er", "es", "st", "et", "em", "te", "e", "s",
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


_GERMAN_BAD_WORDS: set[str] = {
    # Profanity & insults
    "scheisse", "scheiss", "scheisser", "scheisskerl", "scheissdreck",
    "arschloch", "arsch", "arschgeige", "arschgesicht",
    "hurensohn", "hure", "nutte", "schlampe", "fotze",
    "wichser", "wichsen", "wixer",
    "miststuck", "drecksau", "schweinehund",
    "fick", "ficken", "gefickt", "ficker", "fickfehler",
    "verdammt", "vollidiot", "idiot", "spast", "spasti",
    "depp", "deppen", "kretin", "honk", "penner",
    # Slurs
    "kanake", "neger", "schwuchtel", "tunte",
    "missgeburt", "behindert",
}

GermanProfile = LanguageProfile(
    language_code="de",
    language_name="Deutsch (German)",
    bad_words=_GERMAN_BAD_WORDS,
    stemmer=GermanStemmer(),
    context_rules={},
    min_word_length=2,
    version="1.1.0",
    description="German profanity and toxicity word list with stemmer",
    author="LPTE Contributors",
)
