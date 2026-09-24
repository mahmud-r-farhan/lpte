"""Chinese language pack — particle stemmer, profile, and dictionary."""

from lpte.core.profile import LanguageProfile
from lpte.core.stemmer import Stemmer


class ChineseStemmer(Stemmer):
    """
    Chinese language stemmer.
    Strips grammatical particles, plural markers, and modal auxiliaries.
    """

    PARTICLES = sorted(
        [
            "了吗", "了吧", "了吗", "呢吧",
            "们", "的", "了", "着", "过",
            "吧", "呢", "啊", "呀", "嘛",
            "哇", "啦", "呗", "捏", "儿",
        ],
        key=len,
        reverse=True,
    )

    MIN_STEM_LENGTH = 1

    def stem(self, word: str) -> str:
        if len(word) <= self.MIN_STEM_LENGTH:
            return word

        for p in self.PARTICLES:
            if word.endswith(p) and len(word) - len(p) >= self.MIN_STEM_LENGTH:
                return word[: -len(p)]

        return word


_CHINESE_BAD_WORDS: set[str] = {
    # Severe profanity (脏话 / 粗口)
    "操", "肏", "草", "日", "干",
    "他妈的", "他妈", "妈的", "去你妈的", "去你的", "操你妈", "肏你妈", "草你妈",
    "傻逼", "煞笔", "沙比", "傻b", "sb", "傻子", "白痴", "脑残", "智障",
    "婊子", "贱人", "荡妇", "骚货", "母狗",
    "王八蛋", "王八羔子", "混蛋", "混球", "王八",
    "狗娘养的", "狗崽子", "狗日的", "狗贼", "走狗", "死全家", "去死",
    "草泥马", "马勒戈壁", "卧槽", "卧考", "我靠", "我操", "握草",
    "屌", "屄", "逼", "鸡巴", "jb", "吊", "骚逼", "逼样",
    "滚蛋", "滚开", "滚粗", "废物", "垃圾", "畜生", "禽兽",
}

# ─── Content Categories ───────────────────────────────────────────────────────
# Slurs and threats escalate severity; profanity is the default.
_CHINESE_WORD_CATEGORIES: dict[str, str] = {
    **{w: "threat" for w in (
        "死全家", "去死",
    )},
    **{w: "slur" for w in (
        "婊子", "贱人", "荡妇", "骚货", "母狗", "脑残",
        "智障", "白痴", "傻子", "畜生", "禽兽",
    )},
    **{w: "sexual" for w in (
        "屌", "屄", "逼", "鸡巴", "jb", "吊",
        "骚逼", "逼样", "操", "肏", "干",
    )},
    **{w: "insult" for w in (
        "废物", "垃圾", "混蛋", "混球", "王八蛋", "王八羔子",
        "王八", "狗娘养的", "狗崽子", "狗日的", "狗贼", "走狗",
        "滚蛋", "滚开", "滚粗", "傻逼", "煞笔", "沙比",
        "傻b", "sb",
    )},
}

ChineseProfile = LanguageProfile(
    language_code="zh",
    language_name="中文 (Chinese)",
    bad_words=_CHINESE_BAD_WORDS,
    stemmer=ChineseStemmer(),
    word_categories=_CHINESE_WORD_CATEGORIES,
    context_rules={
        "日": {"日常", "日子", "日本", "日光", "生日", "明日", "今日", "节日"},
        "草": {"草地", "草原", "除草", "花草", "水草", "青草", "甘草"},
        "干": {"干净", "干燥", "干部", "干活", "干预", "饼干", "主干"},
    },
    min_word_length=1,
    version="1.1.0",
    description="Chinese profanity, vulgarities, and harassment detection profile",
    author="LPTE Contributors",
)
