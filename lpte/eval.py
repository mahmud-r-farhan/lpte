"""
Evaluation harness — measurable accuracy instead of impressions.

Keyword engines are easy to ship and easy to fool. This module runs a small
labelled corpus per language and reports precision, recall and F1, so that:

- a pack change can be validated in CI (`lpte eval --fail-under 0.90`)
- regressions are caught as a number, not a vibe
- the honest accuracy of each language is visible (they are not equal)

Corpus design notes
-------------------
Each entry is (text, expected_toxic). "Expected" is what a human moderator
would decide for a general-audience community — not "does it contain a banned
word". Clean examples deliberately include hard negatives: benign words that
contain or resemble profanity (Scunthorpe cases), technical usage, quoted
discussion, and ordinary sentences in the target script.

The corpus is intentionally small and high-signal: a few hundred carefully
chosen cases per language beat a large noisy set for regression testing.
Extend it as you tune a pack, and keep hard negatives that you have actually
seen cause false positives.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from lpte.core.engine import LpteEngine
from lpte.core.profile import LanguageProfile

# ─── Labelled Corpus ──────────────────────────────────────────────────────────
# (text, expected_toxic)

CLEAN = False
TOXIC = True

ENGLISH: list[tuple[str, bool]] = [
    # ── Clean: ordinary conversation ──────────────────────────────────────────
    ("Hello, how are you today?", CLEAN),
    ("The weather is beautiful", CLEAN),
    ("Can you review my pull request when you get a chance?", CLEAN),
    ("Thanks for the detailed explanation", CLEAN),
    ("Good morning everyone", CLEAN),
    ("The deployment finished and all tests are green", CLEAN),
    ("See you tomorrow at the meeting", CLEAN),
    # ── Clean: hard negatives (Scunthorpe class) ──────────────────────────────
    ("I live in Scunthorpe", CLEAN),
    ("The class assessment was great", CLEAN),
    ("I passed my exam", CLEAN),
    ("The grass is green", CLEAN),
    ("He plays the bass guitar", CLEAN),
    ("Mass production started", CLEAN),
    ("Charles Dickens wrote novels", CLEAN),
    ("Shellfish is delicious", CLEAN),
    ("A butterfly landed on the flower", CLEAN),
    ("The analysis is complete", CLEAN),
    ("Please take out the trash", CLEAN),
    ("The garbage truck is here", CLEAN),
    ("Please kill the background process", CLEAN),
    # "kill" with an inanimate object: technical and idiomatic usage, not a
    # threat. These are the cases that make a bare "kill" rule unusable.
    ("I will kill the process", CLEAN),
    ("I'm going to kill the background job", CLEAN),
    ("this command will kill all docker containers", CLEAN),
    ("the update will kill my old battery", CLEAN),
    ("I will kill time until the train comes", CLEAN),
    ("we gonna kill the mood", CLEAN),
    ("kill the job and clean the db", CLEAN),
    ("I will kill the process and then restart it", CLEAN),
    ("There is a trash can outside", CLEAN),
    ("Cockney accent is hard to imitate", CLEAN),
    ("The peacock spread its feathers", CLEAN),
    ("I need to pass the ball", CLEAN),
    ("Button your coat", CLEAN),
    ("The title of the book is interesting", CLEAN),
    ("Grape juice is sweet", CLEAN),
    ("The compass points north", CLEAN),
    # ── Clean: reclaimed / legitimate identity usage ──────────────────────────
    ("The queer community centre opened", CLEAN),
    ("She studies queer history", CLEAN),
    # ── Toxic: direct profanity ───────────────────────────────────────────────
    ("you are a fucking idiot", TOXIC),
    ("this is bullshit", TOXIC),
    ("what the hell are you doing", TOXIC),
    ("damn it", TOXIC),
    ("shut up", TOXIC),
    # ── Toxic: obfuscated (the point of the normalizer) ───────────────────────
    ("f4ck this bullsh1t", TOXIC),
    ("f.u.c.k you", TOXIC),
    ("f u c k off", TOXIC),
    ("shiiit happens", TOXIC),
    ("you @sshole", TOXIC),
    ("FuCk", TOXIC),
    ("f​u​c​k", TOXIC),  # zero-width spaces
    ("thіs іs ѕhіt", TOXIC),  # Cyrillic homoglyphs
    # ── Toxic: insults / bullying ─────────────────────────────────────────────
    ("you are so stupid and ugly", TOXIC),
    ("nobody likes you", TOXIC),
    ("you are trash", TOXIC),
    # ── Toxic: slurs (must never be missed) ───────────────────────────────────
    ("you nigger", TOXIC),
    ("you faggot", TOXIC),
    ("you retard", TOXIC),
    # ── Toxic: threats ────────────────────────────────────────────────────────
    ("kill yourself", TOXIC),
    ("I will kill you", TOXIC),
    ("go die", TOXIC),
    ("kys", TOXIC),
    # A threat hidden behind a cheaper match. These used to score HIGH on the
    # insult alone while the CRITICAL threat one word later went unreported,
    # because phrase matching was skipped once anything had matched.
    ("you are such an idiot, go kill yourself", TOXIC),
    ("you stupid bitch, im gonna kill you", TOXIC),
    ("hey loser, I will kill you", TOXIC),
    ("I will kill the process and you", TOXIC),
]

BENGALI: list[tuple[str, bool]] = [
    # ── Clean: ordinary Bengali ───────────────────────────────────────────────
    ("আমি বাংলায় কথা বলি", CLEAN),
    ("আজ আবহাওয়া খুব ভালো", CLEAN),
    ("আমার মায়ের হাতের রান্না খুব ভালো", CLEAN),
    ("আমি আমার বোনের সাথে বাজারে গিয়েছিলাম", CLEAN),
    ("গরুর দুধ খুব পুষ্টিকর", CLEAN),
    ("আমি দুধ খাই", CLEAN),
    ("ফোনটা নষ্ট হয়ে গেছে", CLEAN),
    ("খাবার নষ্ট হয়েছে", CLEAN),
    ("নোংরা পানি পরিষ্কার করো", CLEAN),
    ("রুটি পোড়া হয়ে গেছে", CLEAN),
    ("কুকুর পালন করা কঠিন", CLEAN),
    ("আমি মুসলিম", CLEAN),
    ("সে হিন্দু", CLEAN),
    ("হিন্দু ও মুসলিম একসাথে থাকে", CLEAN),
    ("পাগলের মতো হাসছে", CLEAN),
    ("মাদারবোর্ড নষ্ট হয়ে গেছে", CLEAN),
    # ── Toxic: Bengali profanity and slurs ────────────────────────────────────
    ("কুত্তা", TOXIC),
    ("কুত্তারা", TOXIC),
    ("হারামজাদা", TOXIC),
    ("মাদারচোদ", TOXIC),
    ("চোদ", TOXIC),
    ("তুই একটা গাধা", TOXIC),
    ("সে একটা নষ্ট লোক", TOXIC),
    ("তুই নোংরা কথা বলিস", TOXIC),
    # ── Toxic: the forms people actually type ─────────────────────────────────
    # বোকাচোদা is the most common piece of abuse in Bengali chat and was
    # entirely absent: it is a compound that never contains "চোদ" as a
    # standalone token, and the "-া" ending is not (and must not be) stemmed.
    ("তুই একদম বোকাচোদা", TOXIC),
    ("বোকাচোদা", TOXIC),
    ("বোকচোদ", TOXIC),
    ("চোদা", TOXIC),
    ("চুদা", TOXIC),
    ("খানকির পোলা", TOXIC),
    ("তুই সালা", TOXIC),
    ("সালা কি করিস", TOXIC),
    # ── Clean: the -া ending must NOT be stemmed ──────────────────────────────
    # "বালা" means bangle; stripping the trailing -া to catch "বাল" would
    # flag jewellery. These guard that decision.
    ("আমি ভাত খাই", CLEAN),
    ("তুমি কেমন আছো", CLEAN),
    ("আমার বোন স্কুলে যায়", CLEAN),
]

HINDI: list[tuple[str, bool]] = [
    ("नमस्ते दोस्त", CLEAN),
    ("आज मौसम बहुत अच्छा है", CLEAN),
    ("मैं ठीक हूँ धन्यवाद", CLEAN),
    ("कृपया मेरी मदद करें", CLEAN),
    ("मादरचोद", TOXIC),
    ("तू बहनचोद है", TOXIC),
    ("चूतिया", TOXIC),
    ("साले क्या कर रहा है", TOXIC),
    ("तू हरामजादा है", TOXIC),
]

SPANISH: list[tuple[str, bool]] = [
    ("Hola, ¿cómo estás?", CLEAN),
    ("El clima está hermoso hoy", CLEAN),
    ("Gracias por tu ayuda", CLEAN),
    ("Buenos días a todos", CLEAN),
    ("chinga tu madre", TOXIC),
    ("eres un pendejo", TOXIC),
    ("qué mierda es esta", TOXIC),
    ("puta madre", TOXIC),
    ("eres un idiota", TOXIC),
]

FRENCH: list[tuple[str, bool]] = [
    ("Bonjour, comment allez-vous ?", CLEAN),
    ("Il fait très beau aujourd'hui", CLEAN),
    ("Merci beaucoup pour votre aide", CLEAN),
    ("Bonne journée à tous", CLEAN),
    ("ferme ta gueule", TOXIC),
    ("putain mais quoi", TOXIC),
    ("espèce de connard", TOXIC),
    ("tu es vraiment débile", TOXIC),
]

GERMAN: list[tuple[str, bool]] = [
    ("Guten Tag, wie geht es Ihnen?", CLEAN),
    ("Das Wetter ist heute schön", CLEAN),
    ("Vielen Dank für Ihre Hilfe", CLEAN),
    ("Einen schönen Tag noch", CLEAN),
    ("du arschloch", TOXIC),
    ("verdammte scheisse", TOXIC),
    ("du bist ein idiot", TOXIC),
    ("halt die fresse", TOXIC),
]

RUSSIAN: list[tuple[str, bool]] = [
    ("Привет, как дела?", CLEAN),
    ("Сегодня хорошая погода", CLEAN),
    ("Спасибо за помощь", CLEAN),
    ("Доброе утро всем", CLEAN),
    ("сука блять", TOXIC),
    ("пошел нахуй", TOXIC),
    ("ты мудак", TOXIC),
    ("идиот ебаный", TOXIC),
]

CHINESE: list[tuple[str, bool]] = [
    ("你好，今天天气真好", CLEAN),
    ("谢谢你帮我", CLEAN),
    ("我们一起去散步吧", CLEAN),
    ("祝你有个美好的一天", CLEAN),
    ("草泥马", TOXIC),
    ("你这个傻逼", TOXIC),
    ("他妈的", TOXIC),
    ("去死吧", TOXIC),
]

JAPANESE: list[tuple[str, bool]] = [
    ("こんにちは、今日は良い天気ですね", CLEAN),
    ("ありがとうございました", CLEAN),
    ("美味しい豚肉を食べました", CLEAN),
    ("ゴミ箱を捨てた", CLEAN),
    ("死ね", TOXIC),
    ("くそ野郎", TOXIC),
    ("バカじゃないの", TOXIC),
    ("この豚", TOXIC),
]

KOREAN: list[tuple[str, bool]] = [
    ("안녕하세요 오늘 날씨가 좋습니다", CLEAN),
    ("감사합니다", CLEAN),
    ("좋은 하루 보내세요", CLEAN),
    ("도와주셔서 감사합니다", CLEAN),
    ("씨발 개새끼", TOXIC),
    ("병신아", TOXIC),
    ("닥쳐", TOXIC),
    ("꺼져", TOXIC),
]

ARABIC: list[tuple[str, bool]] = [
    ("مرحبا كيف حالك", CLEAN),
    ("الطقس جميل اليوم", CLEAN),
    ("شكرا لمساعدتك", CLEAN),
    ("صباح الخير", CLEAN),
    ("يا ابن الكلب", TOXIC),
    ("شرموطة", TOXIC),
    ("كلب", TOXIC),
    ("اخرس", TOXIC),
]

EVAL_SETS: dict[str, list[tuple[str, bool]]] = {
    "en": ENGLISH,
    "bn": BENGALI,
    "hi": HINDI,
    "es": SPANISH,
    "fr": FRENCH,
    "de": GERMAN,
    "ru": RUSSIAN,
    "zh": CHINESE,
    "ja": JAPANESE,
    "ko": KOREAN,
    "ar": ARABIC,
}


# ─── Metrics ──────────────────────────────────────────────────────────────────

@dataclass
class EvalReport:
    """Accuracy metrics for one language."""

    language: str
    total: int
    true_positives: int
    false_positives: int
    true_negatives: int
    false_negatives: int
    false_positive_examples: list[str] = field(default_factory=list)
    false_negative_examples: list[str] = field(default_factory=list)

    @property
    def precision(self) -> float:
        if not self.total:
            # No evidence — never report a score that could pass a CI gate.
            return 0.0
        predicted = self.true_positives + self.false_positives
        return self.true_positives / predicted if predicted else 1.0

    @property
    def recall(self) -> float:
        if not self.total:
            return 0.0
        actual = self.true_positives + self.false_negatives
        return self.true_positives / actual if actual else 1.0

    @property
    def f1(self) -> float:
        p, r = self.precision, self.recall
        return 2 * p * r / (p + r) if (p + r) else 0.0

    @property
    def accuracy(self) -> float:
        if not self.total:
            return 0.0
        return (self.true_positives + self.true_negatives) / self.total

    def as_dict(self) -> dict[str, object]:
        return {
            "language": self.language,
            "total": self.total,
            "accuracy": round(self.accuracy, 4),
            "precision": round(self.precision, 4),
            "recall": round(self.recall, 4),
            "f1": round(self.f1, 4),
            "true_positives": self.true_positives,
            "false_positives": self.false_positives,
            "true_negatives": self.true_negatives,
            "false_negatives": self.false_negatives,
            "false_positive_examples": self.false_positive_examples,
            "false_negative_examples": self.false_negative_examples,
        }


# ─── Runner ───────────────────────────────────────────────────────────────────

def evaluate(
    profile: LanguageProfile,
    cases: list[tuple[str, bool]],
    threshold: float = 0.6,
    language_code: str = "",
) -> EvalReport:
    """Run a labelled corpus against one engine and return metrics."""
    engine = LpteEngine(profile, cache_size=0)
    report = EvalReport(
        language=language_code or profile.language_code,
        total=len(cases),
        true_positives=0, false_positives=0,
        true_negatives=0, false_negatives=0,
    )
    for text, expected in cases:
        actual = engine.analyze(text, threshold).is_toxic
        if actual and expected:
            report.true_positives += 1
        elif actual and not expected:
            report.false_positives += 1
            report.false_positive_examples.append(text)
        elif not actual and expected:
            report.false_negatives += 1
            report.false_negative_examples.append(text)
        else:
            report.true_negatives += 1
    return report


def evaluate_all(
    profiles: dict[str, LanguageProfile],
    threshold: float = 0.6,
) -> dict[str, EvalReport]:
    """Evaluate every language that has both a profile and a corpus."""
    reports: dict[str, EvalReport] = {}
    for code, cases in EVAL_SETS.items():
        profile = profiles.get(code)
        if profile is None:
            continue
        reports[code] = evaluate(profile, cases, threshold, language_code=code)
    return reports


def overall(reports: dict[str, EvalReport]) -> EvalReport:
    """Aggregate per-language reports into one."""
    total = EvalReport(
        language="ALL", total=0, true_positives=0, false_positives=0,
        true_negatives=0, false_negatives=0,
    )
    for r in reports.values():
        total.total += r.total
        total.true_positives += r.true_positives
        total.false_positives += r.false_positives
        total.true_negatives += r.true_negatives
        total.false_negatives += r.false_negatives
        total.false_positive_examples.extend(
            f"[{r.language}] {t}" for t in r.false_positive_examples
        )
        total.false_negative_examples.extend(
            f"[{r.language}] {t}" for t in r.false_negative_examples
        )
    return total
