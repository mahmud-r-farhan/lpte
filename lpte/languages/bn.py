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
    "ধোন", "গুদ", "পোদ", "মুতা",

    # ── Slurs / dehumanizing ──────────────────────────────────────────────────
    "মুর্গা", "পোকা", "জন্তু", "জানোয়ার",

    # ── Severe compound (kept intact — these are unambiguous slurs) ───────────
    "মাদারচোদ", "মাচোদ", "ভাগিনাচোদ", "মায়েরচোদ", "বোনচোদ",

    # ── Threats ───────────────────────────────────────────────────────────────
    "মেরে", "খুন", "হত্যা",
}
# REMOVED (false-positive sources — these are ordinary, innocent words):
#   "মায়ের", "বোনের", "বাপের" — bare possessives meaning "mother's" /
#       "sister's" / "father's". They flagged everyday sentences such as
#       "আমার মায়ের হাতের রান্না খুব ভালো" (my mother's cooking is lovely).
#       The actual slurs are the compounds (মাদারচোদ, বোনচোদ …), which are kept.
#   "হিন্দু", "মুসলিম" — religious identity words. Flagging someone for saying
#       "আমি মুসলিম" (I am Muslim) is a fairness failure, not moderation.
#   "দুধ" — simply means "milk"; flagged "আমি দুধ খাই" (I drink milk).

# ─── Content Categories ───────────────────────────────────────────────────────
_BENGALI_WORD_CATEGORIES: dict[str, str] = {
    **{w: "slur" for w in (
        "হারামি", "হারামজাদা", "জারজ", "বেশ্যা", "পতিতা", "রান্ডি",
        "খানকি", "মাগি", "মাদারচোদ", "মাচোদ", "ভাগিনাচোদ",
        "মায়েরচোদ", "বোনচোদ", "মাদার",
    )},
    **{w: "threat" for w in ("খুন", "হত্যা", "মেরে")},
    **{w: "sexual" for w in (
        "চুদ", "চোদ", "চুদি", "চোদন", "চুদাচুদি", "বাল", "বালদের",
        "বালের", "ধোন", "গুদ", "পোদ", "মুতা", "ভোদ", "পোঁদ",
    )},
}

BengaliProfile = LanguageProfile(
    language_code="bn",
    language_name="বাংলা (Bengali)",
    bad_words=_BENGALI_BAD_WORDS,
    stemmer=BengaliStemmer(),
    word_categories=_BENGALI_WORD_CATEGORIES,
    context_rules={
        # "পাগল" (crazy) has softer idiomatic usage
        "পাগল": {"পাগলামি", "পাগলের মতো"},
        # Animal nouns double as insults; the benign collocations below are
        # everyday agricultural / domestic / descriptive usage. The classifier
        # only suppresses when the word's occurrence is covered by one of them.
        "গরু": {"গরুর দুধ", "গরুর গাড়ি", "গরুর মাংস", "গরু পালন", "গরুর খামার"},
        "ছাগল": {"ছাগল পালন", "ছাগলের দুধ", "ছাগলের মাংস", "ছাগলের খামার"},
        "গাধা": {"গাধার দুধ", "গাধা পালন"},
        "কুকুর": {"কুকুর পালন", "কুকুরের খাবার", "কুকুর ছানা", "কুকুর প্রশিক্ষণ"},
        "কুত্তা": {"কুত্তা পালন", "কুত্তার ছানা", "কুত্তার খাবার"},
        "পোকা": {"পোকা মাকড়", "পোকার কামড়", "পোকা তাড়ানোর"},
        "মুরগি": {"মুরগির মাংস", "মুরগি পালন"},
        # "মাদার" is a transliteration of "mother" — benign in these usages
        "মাদার": {"মাদারবোর্ড", "মাদার বোর্ড", "মাদার টেরিজা"},
        # "মেরে" = "having hit/struck" — benign in sports and everyday usage
        "মেরে": {"বল মেরে", "লাথি মেরে", "ঘুষি মেরে", "ছুরি মেরে"},
        # "খুন" appears in news/legal reporting as well as threats
        "খুন": {"খুনের মামলা", "খুনের তদন্ত", "খুন মামলা"},
        # Descriptive adjectives that are only insulting when applied to a
        # person. Everyday usage ("the phone broke", "dirty water") must pass.
        "নষ্ট": {
            "নষ্ট হয়ে", "নষ্ট হয়েছে", "নষ্ট হচ্ছে", "নষ্ট হওয়া",
            "নষ্ট করে ফেলেছে", "সময় নষ্ট", "খাবার নষ্ট",
        },
        "পোড়া": {"পোড়া হয়ে", "পোড়া হয়েছে", "পোড়া মাটি", "পোড়া রুটি", "পোড়া কাঠ"},
        "নোংরা": {
            "নোংরা পানি", "নোংরা জামা", "নোংরা কাপড়", "নোংরা হয়েছে",
            "নোংরা ময়লা", "নোংরা রাস্তা",
        },
        "হারাম": {"হারাম না", "সময় হারাম", "হারাম খাওয়া"},
    },
    min_word_length=2,
    version="1.2.0",
    description=(
        "Bengali profanity and toxicity word list with inflectional stemmer. "
        "Possessive forms, religious identity words and common nouns that "
        "caused false positives were removed in v1.2.0."
    ),
    author="LPTE Contributors",
)
