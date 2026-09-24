"""Japanese language pack — stemmer, profile, and dictionary."""

from lpte.core.profile import LanguageProfile
from lpte.core.stemmer import Stemmer
from lpte.languages.categories import categories_for


class JapaneseStemmer(Stemmer):
    """
    Japanese language stemmer.
    Strips common politeness auxiliaries, verb conjugations, and sentence-ending particles.
    """

    SUFFIXES = sorted(
        [
            # Politeness and past forms (longest first)
            "でございました",
            "ございました",
            "ではありません",
            "じゃありません",
            "ませんでした",
            "ありました",
            "でしょう",
            "だろう",
            "でした",
            "ません",
            "ました",
            "ですね",
            "ですよ",
            "ます",
            "です",
            "だっ",
            "ない",
            "たい",
            "てる",
            "てた",
            "んだ",
            "らし",
            # Plural and diminutive suffixes
            "たち",
            "ら",
            "ども",
            "め",
            # Sentence-ending particles
            "さ",
            "ね",
            "よ",
            "な",
            "ぞ",
            "わ",
            "ぜ",
            "か",
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


_JAPANESE_BAD_WORDS: set[str] = {
    # Death threats & extreme insults
    "死ね",
    "殺す",
    "殺せ",
    "くたばれ",
    "消えろ",
    "死に晒せ",
    "自殺しろ",
    # Profanity & vulgarities (Hiragana, Katakana, Kanji)
    "くそ",
    "クソ",
    "糞",
    "くそ野郎",
    "クソ野郎",
    "くそばばあ",
    "くそじじい",
    "ばか",
    "バカ",
    "馬鹿",
    "大馬鹿",
    "あほ",
    "アホ",
    "阿呆",
    "きちがい",
    "キチガイ",
    "気違い",
    "基地外",
    "変態",
    "ヘンタイ",
    "へんたい",
    "痴漢",
    "ちかん",
    "チカン",
    "雑魚",
    "ざこ",
    "ザコ",
    "カス",
    "かす",
    "屑",
    "クズ",
    "くず",
    "ゴミ",
    "ごみ",
    "豚",
    "ブタ",
    "ぶた",
    "蛆虫",
    "うじむし",
    "淫乱",
    "いんらん",
    "売春婦",
    "娼婦",
    "ヤリマン",
    "やりまん",
    "童貞",
    "処女",
    "チンポ",
    "ちんぽ",
    "チンコ",
    "ちんこ",
    "まんこ",
    "マンコ",
    "ガキ",
    "餓鬼",
    "クソガキ",
    "負け犬",
    "ガイジ",
}

JapaneseProfile = LanguageProfile(
    language_code="ja",
    language_name="日本語 (Japanese)",
    bad_words=_JAPANESE_BAD_WORDS,
    stemmer=JapaneseStemmer(),
    word_categories=categories_for("ja", _JAPANESE_BAD_WORDS),
    context_rules={
        "豚": {"豚肉", "豚骨", "豚汁", "養豚", "黒豚", "酢豚"},
        "ゴミ": {"ゴミ箱", "ゴミ袋", "ゴミ収集", "ゴミ分別"},
        "ごみ": {"ごみ箱", "ごみ袋", "ごみ収集", "ごみ分別"},
    },
    min_word_length=1,
    version="1.2.0",
    description="Japanese profanity, slurs, insults, and harassment detection profile",
    author="LPTE Contributors",
)
