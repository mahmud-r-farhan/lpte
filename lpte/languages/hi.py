"""Hindi language pack — stemmer, profile, and dictionary."""

from lpte.core.profile import LanguageProfile
from lpte.core.stemmer import Stemmer


class HindiStemmer(Stemmer):
    """
    Hindi language stemmer. Strips inflectional suffixes in Devanagari script.
    """

    SUFFIXES = sorted(
        [
            "िस्तानी", "स्तान",
            "वाला", "वाली", "वाले",
            "ताएं", "ताओं", "ता", "ती", "ते",
            "करके", "कर", "ना", "ने", "नी",
            "ाएं", "ाओं", "ियों", "ियों", "ियां",
            "ों", "े", "ा", "ी", "ीं", "ू", "ो",
            "िया", "या", "ये", "ए", "एं",
        ],
        key=len,
        reverse=True,
    )

    MIN_STEM_LENGTH = 2

    def stem(self, word: str) -> str:
        if len(word) < self.MIN_STEM_LENGTH + 2:
            return word

        for suffix in self.SUFFIXES:
            if word.endswith(suffix) and len(word) - len(suffix) >= self.MIN_STEM_LENGTH:
                return word[: -len(suffix)]

        return word


_HINDI_BAD_WORDS: set[str] = {
    # Slurs and severe profanity
    "मादरचोद", "मादर", "मादरजात",
    "बहनचोद", "भेनचोद", "भोसड़ीके", "भोसडीके", "भोसड़ी", "भोसडी",
    "गांडू", "गांड", "गांडमरा", "गांडमस्ती",
    "लौंडा", "लौंडे", "लौंडिया", "लंड", "झांट", "झाँट",
    "कमीना", "कमीने", "कमीनी",
    "साला", "साले", "साली",
    "हरामी", "हरामजादा", "हरामजादी", "हरामज़ादा",
    "कुत्ता", "कुत्ते", "कुत्ती", "कुतिया",
    "सूअर", "सूअरके", "सुअर",
    "रांड", "रंडी", "रान्ड",
    "खानकी", "मागी", "वेश्या",
    "छिनाल", "छक्का", "हिजड़ा",
    "बकचोद", "बकचोदी", "चूतिया", "चूत", "चुतिया", "चूतिये",
    "पागल", "गधा", "उल्लू", "नालायक", "बेशरम",
}

HindiProfile = LanguageProfile(
    language_code="hi",
    language_name="हिन्दी (Hindi)",
    bad_words=_HINDI_BAD_WORDS,
    stemmer=HindiStemmer(),
    context_rules={
        "कुत्ता": {"पिल्ला", "कुत्तेपालक"},
    },
    min_word_length=2,
    version="1.1.0",
    description="Hindi profanity and toxicity word list with Devanagari stemmer",
    author="LPTE Contributors",
)
