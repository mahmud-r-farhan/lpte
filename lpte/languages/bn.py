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
            # Honorific suffixes
            "জি", "সাহেব", "বাবু",
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


# ─── Bengali Profanity Dictionary ─────────────────────────────────────────────
# Root forms only — inflections are handled by the stemmer.
_BENGALI_BAD_WORDS: set[str] = {
    # ── General profanity ──────────────────────────────────────────────────────
    "মাদার", "ভোদ", "বোনিয়া", "পোঁদ", "গাধা", "পাগল",
    "হারামি", "হারাম", "কুত্তা", "কুকুর", "শুয়োর", "পোড়া",
    "বেশ্যা", "পতিতা", "রান্ডি", "খানকি", "মাগি",
    "বদমাশ", "নষ্ট", "ছিনাল", "লুচ্চা", "লম্পট",
    "নোংরা", "ছাগল", "গরু", "পাঁঠা",
    "শালা", "শালি", "হারামজাদা", "জারজ",

    # ── Sexual / vulgar ────────────────────────────────────────────────────────
    "চুদ", "চোদ", "চুদি", "চোদন", "চুদাচুদি",
    "বাল", "বালদের", "বালের",
    "ধোন", "দুধ", "গুদ", "পোদ", "মুতা",

    # ── Slurs / dehumanizing ──────────────────────────────────────────────────
    "মুর্গা", "পোকা", "জন্তু", "জানোয়ার",
    "হিন্দু", "মুসলিম",   # only when used as slurs in context

    # ── Severe compound ───────────────────────────────────────────────────────
    "মাদারচোদ", "বোনের", "মায়ের", "বাপের",
    "মাচোদ", "ভাগিনাচোদ", "মায়েরচোদ",

    # ── Threats ───────────────────────────────────────────────────────────────
    "মেরে", "খুন", "হত্যা",
}

BengaliProfile = LanguageProfile(
    language_code="bn",
    language_name="বাংলা (Bengali)",
    bad_words=_BENGALI_BAD_WORDS,
    stemmer=BengaliStemmer(),
    context_rules={
        # "গরু" can appear in agricultural/food contexts — only flag standalone
        "পাগল": {"পাগলামি", "পাগলের মতো"},  # softer idiomatic usage
    },
    min_word_length=2,
    version="1.1.0",
    description="Bengali profanity and toxicity word list with inflectional stemmer",
    author="LPTE Contributors",
)
