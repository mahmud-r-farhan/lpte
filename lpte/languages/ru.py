"""Russian language pack — stemmer, profile, and dictionary."""

from lpte.core.profile import LanguageProfile
from lpte.core.stemmer import Stemmer


class RussianStemmer(Stemmer):
    """
    Russian language stemmer.
    Strips inflectional suffixes for nouns, verbs, adjectives in Cyrillic.
    """

    SUFFIXES = sorted(
        [
            # Participles / gerunds
            "ившися", "ывшися", "ившись", "ывшись",
            "ившийся", "ывшийся", "ящегося", "ющего", "ущего",
            "ивший", "ывший", "вшись", "вшись",
            # Adjective endings
            "ейшего", "ейшая", "ейшее", "ейшие", "ейший",
            "ий", "ый", "ой", "ая", "яя", "ое", "ее", "ые", "ие", "ых", "их",
            "ому", "ему", "ыми", "ими", "ого", "его", "ую", "юю",
            # Verb reflexive and conjugations
            "вшись", "вшись", "лись", "лась", "лось", "лося", "лися",
            "ется", "ются", "ится", "ятся", "тись", "ться",
            "ешь", "ишь", "ете", "ите", "ем", "им", "ут", "ют", "ат", "ят",
            "ала", "яла", "ила", "ыла", "ела", "али", "яли", "или", "ыли", "ели",
            "ать", "ять", "ить", "ыть", "еть", "уть",
            "ся", "сь", "ло", "ла", "ли",
            # Noun endings & plurals
            "ами", "ями", "ов", "ев", "ей", "ам", "ям", "ах", "ях",
            "ом", "ем", "ой", "ей", "ью", "ия", "ие", "ий", "ья", "ье",
            "а", "я", "о", "е", "и", "ы", "у", "ю", "ь",
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


_RUSSIAN_BAD_WORDS: set[str] = {
    # Russian Mat (мат) & obscenities
    "хуй", "хуя", "хуе", "хуем", "хую", "хуи", "хуев", "хуями", "хуях",
    "хуйня", "хуйни", "хуйне", "хуйню", "хуйней",
    "хуесос", "хуесосы", "хуеплет", "охуеть", "охуел", "охуела", "ахуеть",
    "пизда", "пизды", "пизде", "пизду", "пиздой", "пиздец", "пиздежа",
    "пиздеть", "пиздюк", "пиздобол", "распиздяй",
    "ебать", "ебет", "ебут", "ебал", "ебала", "ебали", "ебаный", "ебаная",
    "ебанутый", "ебанутая", "заебал", "заебала", "заебись", "еблан", "ебло",
    "блять", "блядь", "бляди", "бля", "блядина",
    "сука", "суки", "сучка", "сучара", "сучий",
    "мудак", "мудаки", "мудила", "гондон", "гандон", "гандоны",
    "пидор", "пидорас", "пидорасы", "педик", "гомик",
    "шлюха", "шлюхи", "проститутка", "курва",
    "ублюдок", "ублюдки", "тварь", "твари", "мразь", "мрази",
    "долбоеб", "долбоёб", "долбоебы",
    "дерьмо", "говно", "говнюк", "козел", "козлина",
    "дебил", "дебилы", "идиот", "идиотка", "кретин",
}

RussianProfile = LanguageProfile(
    language_code="ru",
    language_name="Русский (Russian)",
    bad_words=_RUSSIAN_BAD_WORDS,
    stemmer=RussianStemmer(),
    context_rules={
        "сука": {"собака", "кинология"},
    },
    min_word_length=2,
    version="1.1.0",
    description="Russian profanity, Mat expressions, and toxicity profile with Cyrillic stemmer",
    author="LPTE Contributors",
)
