"""Korean language pack — stemmer, profile, and dictionary."""

from lpte.core.profile import LanguageProfile
from lpte.core.stemmer import Stemmer


class KoreanStemmer(Stemmer):
    """
    Korean language stemmer.
    Strips inflectional verb/adjective endings and postposition particles (Josa/Eomi).
    """

    SUFFIXES = sorted(
        [
            # Formal and polite verb endings (longest first)
            "하시겠습니까", "하겠습니다", "하였습니다", "하셨습니다",
            "했습니다", "합니다", "습니다", "입니다", "습니까", "입니까",
            "었어요", "았어요", "였어요", "데요", "네요", "군요",
            "었다", "았다", "였다", "는다", "ㄴ다", "구나", "잖아", "거든",
            "는데", "으면", "라면", "지만", "니까", "어서", "아서",
            # Plural & particle markers
            "들에게", "들한테", "들에서", "들로", "들이", "들은", "들을", "들",
            "에게", "한테", "에서", "으로", "로",
            "은", "는", "이", "가", "을", "를", "도", "만", "과", "와",
            "아", "야", "지",
        ],
        key=len,
        reverse=True,
    )

    MIN_STEM_LENGTH = 1

    def stem(self, word: str) -> str:
        if len(word) <= self.MIN_STEM_LENGTH:
            return word

        for suffix in self.SUFFIXES:
            if word.endswith(suffix) and len(word) - len(suffix) >= self.MIN_STEM_LENGTH:
                return word[: -len(suffix)]

        return word


_KOREAN_BAD_WORDS: set[str] = {
    # Severe profanity (욕설)
    "씨발", "시발", "시팔", "씨팔", "개씨발", "씨발년", "씨발놈", "씨발새끼",
    "씹", "씹창", "씹새", "씹새끼", "씹자식",
    "개새끼", "새끼", "개자식", "개련", "개놈", "개년", "개소리",
    "좆", "좆까", "좆같", "좆만한", "좆나", "존나", "졸라", "좆밥",
    "병신", "븅신", "병신새끼", "등신", "호구",
    "지랄", "지랄하네", "염병", "옘병", "엠창",
    "미친놈", "미친년", "미친새끼", "또라이", "미친",
    "닥쳐", "닥쳐라", "꺼져", "꺼져라", "뒤져", "뒤져라", "죽어", "죽여",
    "쌍놈", "쌍년", "화냥년", "창녀", "걸레", "보지", "자지", "육시랄",
    "쓰레기", "폐기물", "패륜아", "틀딱", "한남충", "메갈", "일베",
}

# ─── Content Categories ───────────────────────────────────────────────────────
# Slurs and threats escalate severity; profanity is the default.
_KOREAN_WORD_CATEGORIES: dict[str, str] = {
    **{w: "threat" for w in (
        "죽어", "죽여", "뒤져", "뒤져라",
    )},
    **{w: "slur" for w in (
        "병신", "븅신", "병신새끼", "등신", "한남충", "메갈",
        "일베", "쌍놈", "쌍년", "화냥년", "창녀", "걸레",
        "패륜아",
    )},
    **{w: "sexual" for w in (
        "씹", "씹창", "씹새", "씹새끼", "씹자식", "좆",
        "좆까", "좆같", "좆만한", "좆나", "존나", "졸라",
        "좆밥", "보지", "자지",
    )},
    **{w: "insult" for w in (
        "개새끼", "새끼", "개자식", "개련", "개놈", "개년",
        "개소리", "지랄", "지랄하네", "염병", "옘병", "엠창",
        "미친놈", "미친년", "미친새끼", "또라이", "미친", "닥쳐",
        "닥쳐라", "꺼져", "꺼져라", "쓰레기", "폐기물", "틀딱",
        "호구",
    )},
}

KoreanProfile = LanguageProfile(
    language_code="ko",
    language_name="한국어 (Korean)",
    bad_words=_KOREAN_BAD_WORDS,
    stemmer=KoreanStemmer(),
    word_categories=_KOREAN_WORD_CATEGORIES,
    context_rules={
        "쓰레기": {"쓰레기통", "쓰레기봉투", "분리수거"},
        "개": {"강아지", "개과", "사냥개", "안내견"},
    },
    min_word_length=1,
    version="1.1.0",
    description="Korean profanity, insults, slurs, and harassment detection profile",
    author="LPTE Contributors",
)
