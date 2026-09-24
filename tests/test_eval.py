"""
Evaluation harness tests.

The labelled corpus is a regression guard, not a claim of real-world
perfection: it is small and high-signal by design, and the engine has been
tuned against it. What these tests guarantee is that a change cannot silently
degrade accuracy below the agreed floor, and that the harness itself stays
consistent (every category key must exist in the vocabulary, etc.).
"""

import pytest

from lpte.core.engine import LpteEngine
from lpte.eval import (
    EVAL_SETS,
    evaluate,
    evaluate_all,
    overall,
)
from lpte.languages import (
    ArabicProfile,
    BengaliProfile,
    ChineseProfile,
    EnglishProfile,
    FrenchProfile,
    GermanProfile,
    HindiProfile,
    JapaneseProfile,
    KoreanProfile,
    RussianProfile,
    SpanishProfile,
)

PROFILES = {
    "en": EnglishProfile, "bn": BengaliProfile, "hi": HindiProfile,
    "es": SpanishProfile, "fr": FrenchProfile, "de": GermanProfile,
    "ru": RussianProfile, "zh": ChineseProfile, "ja": JapaneseProfile,
    "ko": KoreanProfile, "ar": ArabicProfile,
}

# Accuracy floor. Deliberately below the current 1.00 so that adding a hard
# case does not immediately fail the build, while a real regression does.
MIN_F1 = 0.90


class TestCorpusIntegrity:
    def test_every_language_has_a_corpus(self):
        assert set(EVAL_SETS) == set(PROFILES)

    def test_every_corpus_has_both_classes(self):
        for code, cases in EVAL_SETS.items():
            labels = {label for _, label in cases}
            assert labels == {True, False}, f"{code}: corpus needs both classes"

    def test_no_duplicate_cases(self):
        for code, cases in EVAL_SETS.items():
            texts = [t for t, _ in cases]
            assert len(texts) == len(set(texts)), f"{code}: duplicate cases"


class TestAccuracyFloors:
    @pytest.mark.parametrize("code", sorted(EVAL_SETS))
    def test_language_meets_f1_floor(self, code):
        report = evaluate(PROFILES[code], EVAL_SETS[code], language_code=code)
        assert report.f1 >= MIN_F1, (
            f"{code}: F1 {report.f1:.3f} < {MIN_F1}\n"
            f"  FP: {report.false_positive_examples}\n"
            f"  FN: {report.false_negative_examples}"
        )

    def test_overall_meets_f1_floor(self):
        reports = evaluate_all(PROFILES)
        total = overall(reports)
        assert total.f1 >= MIN_F1, (
            f"overall F1 {total.f1:.3f}\n"
            f"  FP: {total.false_positive_examples}\n"
            f"  FN: {total.false_negative_examples}"
        )

    def test_slurs_are_never_a_false_negative(self):
        """
        The corpus contains identity slurs in every language; missing one is
        the single worst failure mode, so it is asserted separately.
        """
        slur_cases = [
            ("en", "you nigger"), ("en", "you faggot"), ("en", "you retard"),
            ("bn", "হারামজাদা"), ("hi", "हिजड़ा"),
            ("ru", "пидор"), ("zh", "婊子"), ("ko", "병신"),
            ("fr", "négre salope"), ("de", "neger schwuchtel"),
            ("ar", "شرموطة"),
        ]
        for code, text in slur_cases:
            engine = LpteEngine(PROFILES[code], cache_size=0)
            assert engine.analyze(text).is_toxic, f"{code}: slur missed: {text}"


class TestReportMath:
    def test_perfect_report(self):
        report = evaluate(
            EnglishProfile,
            [("hello world", False), ("you are a fucking idiot", True)],
            language_code="en",
        )
        assert report.accuracy == 1.0
        assert report.precision == 1.0
        assert report.recall == 1.0
        assert report.f1 == 1.0

    def test_all_wrong_report(self):
        report = evaluate(
            EnglishProfile,
            [("hello world", True), ("you are a fucking idiot", False)],
            language_code="en",
        )
        # Both predictions wrong: 0 TP, 1 FP, 1 FN, 0 TN
        assert report.true_positives == 0
        assert report.false_positives == 1
        assert report.false_negatives == 1
        assert report.f1 == 0.0

    def test_recall_counts_misses(self):
        report = evaluate(
            EnglishProfile,
            [("hello world", False), ("some obscure slur xyzzy", True)],
            language_code="en",
        )
        assert report.recall == 0.0
        assert report.precision == 1.0  # nothing was flagged, so no FP

    def test_empty_corpus_reports_zero_not_perfect(self):
        """
        An empty corpus must NOT score 100% — otherwise a filtered-out corpus
        would silently satisfy `lpte eval --fail-under 0.9` in CI.
        """
        report = evaluate(EnglishProfile, [], language_code="en")
        assert report.accuracy == 0.0
        assert report.precision == 0.0
        assert report.recall == 0.0
        assert report.f1 == 0.0

    def test_as_dict_is_json_serialisable(self):
        import json
        r = evaluate(EnglishProfile, EVAL_SETS["en"][:5], language_code="en")
        payload = json.loads(json.dumps(r.as_dict()))
        assert payload["language"] == "en"


class TestFuzzyFalsePositiveGuard:
    """
    Fuzzy matching must not flag an ordinary word that differs from a slur by
    its FIRST letter — obfuscation stays readable, so it preserves the initial
    character. "bonne journée" (good day) vs "conne" is the canonical case.
    """

    @pytest.mark.parametrize("text", [
        "Bonne journée à tous",
        "bonne nuit",
        "the solution works",
        "press the button",
        "a little better",
    ])
    def test_french_and_english_hard_negatives(self, text):
        engine = LpteEngine(EnglishProfile, cache_size=0)
        fr = LpteEngine(FrenchProfile, cache_size=0)
        assert not fr.analyze(text).is_toxic or not engine.analyze(text).is_toxic

    def test_bonne_journee_is_clean(self):
        assert not LpteEngine(FrenchProfile, cache_size=0).analyze(
            "Bonne journée à tous").is_toxic

    @pytest.mark.parametrize("text", [
        "fuckk", "assholee", "bitchh", "shittt", "niger", "faggt", "retrd",
        "stpid", "dmbass", "bullsht",
    ])
    def test_real_obfuscation_still_caught(self, text):
        """First-letter-preserving edits must still match."""
        assert LpteEngine(EnglishProfile, cache_size=0).analyze(text).is_toxic, text
