"""Arabic language pack — stemmer, profile, and dictionary."""

from lpte.core.profile import LanguageProfile
from lpte.core.stemmer import Stemmer
from lpte.languages.categories import categories_for


class ArabicStemmer(Stemmer):
    """
    Arabic language stemmer.
    Strips common prefixes (الـ, و, ف, ب, ك, ل, س) and suffixes
    (ـها, ـهم, ـهن, ـكم, ـكن, ـنا, ـي, ـك, ـه, ـة, ـات, ـين, ـون).
    """

    PREFIXES = ("ال", "وال", "فال", "بال", "كال", "لل", "و", "ف", "ب", "ك", "ل", "س")
    SUFFIXES = sorted(
        [
            "تموه",
            "تموها",
            "تموهم",
            "كما",
            "هما",
            "تان",
            "تين",
            "ها",
            "هم",
            "هن",
            "كم",
            "كن",
            "نا",
            "ات",
            "ان",
            "ين",
            "ون",
            "وا",
            "تا",
            "تم",
            "تن",
            "ي",
            "ك",
            "ه",
            "ة",
        ],
        key=len,
        reverse=True,
    )

    MIN_STEM_LENGTH = 2

    def stem(self, word: str) -> str:
        res = word

        # Strip prefixes
        for prefix in self.PREFIXES:
            if res.startswith(prefix) and len(res) - len(prefix) >= self.MIN_STEM_LENGTH:
                res = res[len(prefix) :]
                break

        # Strip suffixes
        for suffix in self.SUFFIXES:
            if res.endswith(suffix) and len(res) - len(suffix) >= self.MIN_STEM_LENGTH:
                res = res[: -len(suffix)]
                break

        return res


_ARABIC_BAD_WORDS: set[str] = {
    # Insults & profanity
    "شرموطة",
    "شرموط",
    "قحبة",
    "منيوك",
    "منيوكة",
    "كس",
    "كسختك",
    "طيز",
    "زب",
    "عرص",
    "ابن الكلب",
    "ابن الحرام",
    "ابن الشرموطة",
    "ابن القحبة",
    "خرا",
    "خراء",
    "وسخ",
    "سافل",
    "حقير",
    "تافه",
    "حمار",
    "لوطي",
    "ديوث",
    "زنديق",
    "ملعون",
    "يلعن",
    "لعنة",
    "اللعنة",
    "تبا",
}

ArabicProfile = LanguageProfile(
    language_code="ar",
    language_name="العربية (Arabic)",
    bad_words=_ARABIC_BAD_WORDS,
    stemmer=ArabicStemmer(),
    word_categories=categories_for("ar", _ARABIC_BAD_WORDS),
    context_rules={},
    min_word_length=2,
    version="1.2.0",
    description="Arabic profanity and toxicity word list with affix-stripping stemmer",
    author="LPTE Contributors",
)
