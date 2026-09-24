"""
Multi-language / code-switched text tests.

Real chat in South Asia is routinely mixed-script ("তুই একদম idiot",
"yeh toh bakwas hai"). Single-language engines miss half of every message.
"""

import pytest

from lpte.core.multilang import MultiLangEngine, detect_scripts
from lpte.languages.bn import BengaliProfile
from lpte.languages.en import EnglishProfile
from lpte.languages.hi import HindiProfile


@pytest.fixture
def bn_en():
    return MultiLangEngine([BengaliProfile, EnglishProfile])


class TestScriptDetection:
    def test_bengali_script(self):
        assert "bn" in detect_scripts("আমি বাংলায় কথা বলি")

    def test_latin_script_yields_latin_languages(self):
        codes = detect_scripts("hello world")
        assert "en" in codes
        assert "bn" not in codes

    def test_mixed_script(self):
        codes = detect_scripts("তুই idiot")
        assert "bn" in codes and "en" in codes

    def test_cyrillic(self):
        assert "ru" in detect_scripts("сука блять")

    def test_cjk(self):
        assert "zh" in detect_scripts("你好世界")

    def test_hangul(self):
        assert "ko" in detect_scripts("안녕하세요")


class TestEngineRouting:
    """Only engines whose script is present should run — cost matters."""

    def test_pure_bengali_runs_only_bengali(self, bn_en):
        assert bn_en._candidate_languages("আমি বাংলায় কথা বলি") == ["bn"]

    def test_pure_english_runs_only_english(self, bn_en):
        assert bn_en._candidate_languages("hello world") == ["en"]

    def test_mixed_runs_both(self, bn_en):
        assert sorted(bn_en._candidate_languages("তুই idiot")) == ["bn", "en"]

    def test_unknown_script_runs_nothing(self, bn_en):
        assert bn_en._candidate_languages("你好世界") == []

    def test_empty_text_runs_nothing(self, bn_en):
        assert bn_en._candidate_languages("") == []


class TestCodeSwitchedDetection:
    def test_bengali_plus_english_insult(self, bn_en):
        result = bn_en.analyze("তুই একদম idiot")
        assert result.is_toxic
        assert "idiot" in result.matched_terms

    def test_bengali_plus_english_profanity(self, bn_en):
        result = bn_en.analyze("তুই একদম fuck")
        assert result.is_toxic

    def test_clean_bengali_passes(self, bn_en):
        assert not bn_en.analyze("আমি বাংলায় কথা বলি").is_toxic

    def test_clean_english_passes(self, bn_en):
        assert not bn_en.analyze("hello how are you").is_toxic

    def test_bengali_profanity_detected(self, bn_en):
        result = bn_en.analyze("কুত্তা")
        assert result.is_toxic
        assert result.language == "bn"

    def test_both_languages_reported_when_both_match(self, bn_en):
        result = bn_en.analyze("কুত্তা you idiot")
        assert result.is_toxic
        assert set(result.language.split(",")) == {"bn", "en"}


class TestMerging:
    def test_worst_severity_wins(self, bn_en):
        per = bn_en.analyze_all("কুত্তা you idiot")
        merged = bn_en.analyze("কুত্তা you idiot")
        assert merged.severity == max(r.severity for r in per.values())

    def test_terms_are_unioned_and_deduplicated(self, bn_en):
        merged = bn_en.analyze("কুত্তা you idiot")
        assert len(merged.matched_terms) == len(set(merged.matched_terms))

    def test_no_matches_returns_clean(self, bn_en):
        merged = bn_en.analyze("আমি বাংলায় কথা বলি")
        assert merged.confidence == 0.0
        assert not merged.is_toxic


class TestMultiLangSanitize:
    def test_masks_english_inside_bengali(self, bn_en):
        out = bn_en.sanitize("তুই একদম idiot")
        assert "idiot" not in out

    def test_masks_bengali(self, bn_en):
        out = bn_en.sanitize("কুত্তা")
        assert "কুত্তা" not in out

    def test_leaves_clean_text_untouched(self, bn_en):
        text = "আমি বাংলায় কথা বলি"
        assert bn_en.sanitize(text) == text


class TestThreeLanguages:
    def test_hinglish(self):
        engine = MultiLangEngine([HindiProfile, EnglishProfile])
        assert engine.analyze("you are such an idiot").is_toxic
        assert not engine.analyze("नमस्ते दोस्त").is_toxic

    def test_requires_at_least_one_profile(self):
        with pytest.raises(ValueError):
            MultiLangEngine([])


class TestCaching:
    def test_repeated_analysis_is_cached(self, bn_en):
        r1 = bn_en.analyze("তুই একদম idiot")
        r2 = bn_en.analyze("তুই একদম idiot")
        assert r1.confidence == r2.confidence
        assert r1.matched_terms == r2.matched_terms
