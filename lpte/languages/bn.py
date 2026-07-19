"""Bengali language pack — stemmer, profile, and dictionary."""

from lpte.core.profile import LanguageProfile
from lpte.core.stemmer import Stemmer


class BengaliStemmer(Stemmer):
    """
    Bengali language stemmer.

    Bengali is highly inflectional with suffixes modifying nouns, verbs,
    and adjectives. This stemmer strips common inflectional suffixes.

    Suffix categories:
    - Case markers: -কে, -র, -ত, -ে, -য়
    - Plurals: -রা, -গুলো, -দের
    - Verb conjugations: -ছি, -ছে, -ছো, -ব, -ল
    - Diminutives: -টা, -টি, -টো
    - Possessives: -টার, -টির, -টাকে
    """

    SUFFIXES = sorted(
        [
            # Possessive + case (longest first for greedy matching)
            "টাকে", "টির", "টার", "টাত", "টিত",
            # Diminutive + case
            "গুলোকে", "গুলোর", "গুলোত", "গুলো",
            "দেরকে", "দেরের", "দেরত", "দের",
            # Plural markers
            "রা", "গণ", "বৃন্দ",
            # Verb endings
            "ছিলাম", "ছিলে", "ছিলো", "ছিল",
            "ছি", "ছে", "ছো", "ছোঁ",
            "বেন", "বে", "বো", "ব",
            "লাম", "লে", "লো", "ল",
            "ন্তি", "ন্তে", "ন্তো", "ন্ত",
            "য়ে", "য়ো", "য়",
            # Case markers
            "কে", "রা", "র", "তে", "ত", "য়ে", "য়", "ে", "ও",
            # Diminutives
            "টা", "টি", "টো",
            # Adjective/adverb endings
            "ময়", "সুল", "পূর্ণ", "শীল",
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


# Bengali profanity dictionary — root forms
_BENGALI_BAD_WORDS: set[str] = {
    # Category: General profanity
    "মাদার", "ভোদ", "বোনিয়া", "পোঁদ", "গাধা", "পাগল",
    "হারামি", "হারাম", "কুত্তা", "কুকুর", "শুয়োর", "পোড়া",
    "বেশ্যা", "পতিতা", "রান্ডি", "খানকি", "মাগি",
    # Category: Sexual/vulgar
    "চুদ", "চোদ", "চুদি", "চোদন", "চুদাচুদি",
    "বাল", "বালদের", "বালের",
    # Category: Slurs and dehumanizing
    "মুর্গা", "পোকা", "জন্তু",
    # Category: Severe
    "মাদারচোদ", "বোনের", "মায়ের", "বাপের",
}

BengaliProfile = LanguageProfile(
    language_code="bn",
    language_name="বাংলা (Bengali)",
    bad_words=_BENGALI_BAD_WORDS,
    stemmer=BengaliStemmer(),
    context_rules={},
    min_word_length=2,
)
