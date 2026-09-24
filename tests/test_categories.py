"""
Content-category tests.

Not all toxicity is equal. A swear, a slur and a death threat need different
responses even when the engine is equally confident about all three.
"""

import pytest

from lpte.core.classifier import Severity
from lpte.core.engine import LpteEngine
from lpte.core.loader import LanguagePackLoader
from lpte.languages.bn import BengaliProfile
from lpte.languages.en import EnglishProfile


@pytest.fixture
def en():
    return LpteEngine(EnglishProfile, cache_size=0)


@pytest.fixture
def bn():
    return LpteEngine(BengaliProfile, cache_size=0)


class TestCategoryAssignment:
    def test_slur_category(self, en):
        assert "slur" in en.analyze("you nigger").categories

    def test_threat_category(self, en):
        assert "threat" in en.analyze("I will kill you").categories

    def test_sexual_category(self, en):
        assert "sexual" in en.analyze("you suck cock").categories

    def test_profanity_is_default(self, en):
        result = en.analyze("this is bullshit")
        assert result.categories == ["profanity"]

    def test_insult_category(self, en):
        assert "insult" in en.analyze("you are so stupid and ugly").categories

    def test_multiple_categories(self, en):
        cats = en.analyze("you stupid nigger").categories
        assert "slur" in cats and "insult" in cats

    def test_clean_text_has_no_categories(self, en):
        assert en.analyze("hello world").categories == []


class TestSeverityEscalation:
    """
    Slurs and threats escalate one level above a plain swear at the same
    confidence — identity attacks warrant a stronger response.
    """

    def test_slur_escalates_above_profanity(self, en):
        swear = en.analyze("this is bullshit")
        slur = en.analyze("you nigger")
        assert slur.severity > swear.severity

    def test_slur_reaches_critical(self, en):
        assert en.analyze("you nigger").severity == Severity.CRITICAL

    def test_threat_escalates(self, en):
        assert en.analyze("I will kill you").severity >= Severity.HIGH

    def test_escalation_is_capped(self, en):
        assert en.analyze("you nigger").severity <= Severity.CRITICAL


class TestCategoriesFromJsonPacks:
    def test_json_pack_categories_are_loaded(self, tmp_path):
        pack = {
            "language_code": "test",
            "language_name": "Testish",
            "bad_words": ["zork", "blarg"],
            "word_categories": {"zork": "threat", "blarg": "insult"},
        }
        path = tmp_path / "test_profile.json"
        path.write_text(
            __import__("json").dumps(pack, ensure_ascii=False), encoding="utf-8"
        )
        profile = LanguagePackLoader.load_file(path)
        engine = LpteEngine(profile, cache_size=0)

        assert engine.analyze("zork").categories == ["threat"]
        assert engine.analyze("blarg").categories == ["insult"]

    def test_missing_category_defaults_to_profanity(self, tmp_path):
        pack = {
            "language_code": "test2",
            "language_name": "Testish 2",
            "bad_words": ["zork"],
        }
        path = tmp_path / "test2_profile.json"
        path.write_text(
            __import__("json").dumps(pack, ensure_ascii=False), encoding="utf-8"
        )
        profile = LanguagePackLoader.load_file(path)
        engine = LpteEngine(profile, cache_size=0)
        assert engine.analyze("zork").categories == ["profanity"]

    def test_invalid_categories_rejected(self, tmp_path):
        import json
        pack = {
            "language_code": "bad",
            "language_name": "Bad",
            "bad_words": ["x"],
            "word_categories": ["not", "a", "dict"],
        }
        path = tmp_path / "bad_profile.json"
        path.write_text(json.dumps(pack), encoding="utf-8")
        with pytest.raises(ValueError):
            LanguagePackLoader.load_file(path)


class TestBengaliCategories:
    def test_bengali_slur_category(self, bn):
        result = bn.analyze("হারামজাদা")
        assert "slur" in result.categories

    def test_bengali_sexual_category(self, bn):
        result = bn.analyze("চোদ")
        assert "sexual" in result.categories


class TestSeverityCalibration:
    """
    Severity must reflect harm, not how many words matched. Confidence counts
    matches, so without an explicit cap two insults would outrank a slur.
    """

    def test_insults_capped_at_high(self, en):
        assert en.analyze("you are so stupid and ugly").severity == Severity.HIGH

    def test_strong_profanity_capped_at_high(self, en):
        assert en.analyze("f4ck this bullsh1t").severity == Severity.HIGH

    def test_slur_can_reach_critical(self, en):
        assert en.analyze("you nigger").severity == Severity.CRITICAL

    def test_threat_can_reach_critical(self, en):
        assert en.analyze("I will kill you").severity == Severity.CRITICAL

    def test_mixed_insult_and_slur_reaches_critical(self, en):
        assert en.analyze("you stupid nigger").severity == Severity.CRITICAL

    def test_insult_never_outranks_slur(self, en):
        insult = en.analyze("you are so stupid and ugly")
        slur = en.analyze("you nigger")
        assert slur.severity > insult.severity


class TestDeterminism:
    def test_matched_terms_order_is_stable(self, en):
        """Set iteration must never leak into output ordering."""
        first = en.analyze("you stupid nigger idiot").matched_terms
        for _ in range(20):
            assert en.analyze("you stupid nigger idiot").matched_terms == first
