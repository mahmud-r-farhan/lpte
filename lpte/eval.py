"""Small labelled regression corpus and precision/recall/F1 evaluation.

These examples are hand-written and overlap with vocabulary development. They
are NOT an external accuracy measurement. For production, label held-out local
traffic and supply it as JSONL via ``lpte eval --cases`` (never send it here).
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path

from lpte.core.classifier import validate_threshold
from lpte.core.engine import LpteEngine
from lpte.core.profile import LanguageProfile

# Each tuple is (text, should_flag). Keep both hard negatives and positives;
# add new cases whenever a rule is changed, particularly for benign compounds.
EVAL_SETS: dict[str, list[tuple[str, bool]]] = {
    "en": [
        ("hello how are you today", False),
        ("the class assessment was great", False),
        ("I passed the exam this morning", False),
        ("I passed the exam. you ass!", True),
        ("please kill the background process", False),
        ("I will kill you", True),
        ("This is a rape prevention class", False),
        ("they identify as queer", False),
        ("well done, nice work", False),
        ("ass!", True),
        ("damn this is good", True),
        ("f4ck this bullsh1t", True),
        ("f.u.c.k", True),
        ("f u c k", True),
        ("shiiit", True),
        ("you are a fucking idiot", True),
        ("you are so stupid and ugly", True),
        ("that was a stupid mistake", False),
        ("you nigger", True),
        ("just kys lol", True),
        ("go die", True),
        ("no one likes you, go away", True),  # semantic abuse: known limitation
    ],
    "bn": [
        ("আমি বাংলায় কথা বলি", False),
        ("আমার মায়ের রান্না ভালো", False),
        ("হিন্দু এবং মুসলিম বন্ধু", False),
        ("দুধ দিয়ে চা বানালাম", False),
        ("আজ পাগলের মতো কাজ করেছি", False),
        ("আজ আবহাওয়া ভালো", False),
        ("কুত্তা", True),
        ("কুত্তারা", True),
        ("হারামি কুত্তা", True),
        ("মাদারচোদ", True),
        ("তোকে মেরে ফেলব", True),
    ],
    "zh": [
        ("你好，今天的天气真好，我们去散步吧", False),
        ("生日快乐", False),
        ("草地上的花很好看", False),
        ("草地上的草，去死", True),
        ("你这个傻逼", True),
        ("草泥马", True),
        ("去死", True),
    ],
    "ja": [
        ("こんにちは！今日はとても良い天気ですね。", False),
        ("美味しい豚肉を食べました", False),
        ("障害者の権利を守る", False),
        ("豚肉と豚", True),
        ("死ね くそ野郎", True),
        ("あいつは本当にバカですね", True),
        ("ガイジ", True),
    ],
    "ko": [
        ("안녕하세요! 오늘 날씨가 참 좋습니다.", False),
        ("방에 쓰레기통을 두었습니다", False),
        ("오늘은 수업이 있어요", False),
        ("야 이 씨발 개새끼야", True),
        ("닥쳐 병신새끼야", True),
        ("죽여", True),
    ],
    "ru": [
        ("Привет! Как твои дела и работа?", False),
        ("Хорошая погода сегодня", False),
        ("ты сука иди нахуй", True),
        ("заебали эти мудаки", True),
        ("блять", True),
    ],
    "es": [
        ("Hola amigo, ¿cómo estás hoy en la casa?", False),
        ("Buenos días a todos", False),
        ("eres un pendejo de mierda", True),
        ("joder", True),
        ("maricon", True),
    ],
    "hi": [
        ("नमस्ते दोस्त, आज का मौसम बहुत अच्छा है", False),
        ("हिजड़ा समुदाय के अधिकार", False),
        ("तू बड़ा कमीना और हरामी है", True),
        ("मादरचोद", True),
        ("छक्का", True),
    ],
    "fr": [
        ("Bonjour monsieur, comment allez-vous aujourd'hui?", False),
        ("bonne journée", False),
        ("ferme ta gueule espèce de connard", True),
        ("merde", True),
        ("creve", True),
    ],
    "de": [
        ("Guten Tag, das Wetter ist heute wirklich schön", False),
        ("Menschen mit Behinderung verdienen Respekt", False),
        ("du verdammtes arschloch", True),
        ("scheisse", True),
        ("kanake", True),
    ],
    "ar": [
        ("السلام عليكم ورحمة الله وبركاته كيف حالك اليوم", False),
        ("هذا كلب بوليسي", False),
        ("يا ابن الكلب يا سافل", True),
        ("قحبة", True),
        ("لوطي", True),
    ],
}


@dataclass
class EvalReport:
    language_code: str
    true_positives: int = 0
    false_positives: int = 0
    true_negatives: int = 0
    false_negatives: int = 0
    false_positive_examples: list[str] = field(default_factory=list)
    false_negative_examples: list[str] = field(default_factory=list)

    @property
    def total(self) -> int:
        return (
            self.true_positives + self.false_positives + self.true_negatives + self.false_negatives
        )

    @property
    def accuracy(self) -> float:
        return (self.true_positives + self.true_negatives) / self.total if self.total else 0.0

    @property
    def precision(self) -> float:
        denom = self.true_positives + self.false_positives
        return self.true_positives / denom if denom else 0.0

    @property
    def recall(self) -> float:
        denom = self.true_positives + self.false_negatives
        return self.true_positives / denom if denom else 0.0

    @property
    def f1(self) -> float:
        denom = 2 * self.true_positives + self.false_positives + self.false_negatives
        return 2 * self.true_positives / denom if denom else 0.0


def load_cases(path: str | Path) -> list[tuple[str, bool]]:
    """Read labelled {"text": string, "toxic": boolean} JSONL, fail fast."""
    cases: list[tuple[str, bool]] = []
    with Path(path).open(encoding="utf-8") as source:
        for line_no, line in enumerate(source, 1):
            if not line.strip():
                continue
            try:
                case = json.loads(line)
            except json.JSONDecodeError as exc:
                raise ValueError(f"{path}:{line_no}: invalid JSON: {exc}") from exc
            if (
                not isinstance(case, dict)
                or not isinstance(case.get("text"), str)
                or not case["text"].strip()
                or type(case.get("toxic")) is not bool
            ):
                raise ValueError(f"{path}:{line_no}: expected {{'text': string, 'toxic': boolean}}")
            cases.append((case["text"], case["toxic"]))
    if not cases:
        raise ValueError(f"{path}: no labelled cases")
    return cases


def evaluate(
    profile: LanguageProfile,
    cases: list[tuple[str, bool]],
    threshold: float = 0.6,
    *,
    language_code: str | None = None,
) -> EvalReport:
    validate_threshold(threshold)
    report = EvalReport(language_code or profile.language_code)
    engine = LpteEngine(profile, threshold, cache_size=0)
    for text, expected in cases:
        actual = engine.is_toxic(text)
        if expected and actual:
            report.true_positives += 1
        elif expected:
            report.false_negatives += 1
            report.false_negative_examples.append(text)
        elif actual:
            report.false_positives += 1
            report.false_positive_examples.append(text)
        else:
            report.true_negatives += 1
    return report


def evaluate_all(
    profiles: dict[str, LanguageProfile],
    threshold: float = 0.6,
) -> dict[str, EvalReport]:
    return {
        code: evaluate(p, EVAL_SETS[code], threshold, language_code=code)
        for code, p in profiles.items()
        if code in EVAL_SETS
    }


def overall(reports: dict[str, EvalReport]) -> EvalReport:
    total = EvalReport("all")
    for report in reports.values():
        total.true_positives += report.true_positives
        total.false_positives += report.false_positives
        total.true_negatives += report.true_negatives
        total.false_negatives += report.false_negatives
        total.false_positive_examples.extend(report.false_positive_examples)
        total.false_negative_examples.extend(report.false_negative_examples)
    return total
