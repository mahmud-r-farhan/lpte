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


class TestBengaliColloquialForms:
    """
    The forms Bengali speakers actually type.

    "বোকাচোদা" is the most common piece of abuse in Bengali chat and used to
    score completely clean: it is a compound that never contains the root
    "চোদ" as a standalone token, and the colloquial "-া" verb ending is not
    stemmed — stripping it would turn "বালা" (bangle) into a vulgar word.
    """

    @pytest.mark.parametrize("text", [
        "বোকাচোদা", "বোকচোদ", "বকচোদ", "তুই একদম বোকাচোদা", "মাদারচোদা",
    ])
    def test_compound_slurs_detected(self, bn, text):
        result = bn.analyze(text)
        assert result.is_toxic, text
        assert "slur" in result.categories, text

    @pytest.mark.parametrize("text", ["চোদা", "চুদা", "চোদি", "চোদবি"])
    def test_conjugated_sexual_forms_detected(self, bn, text):
        result = bn.analyze(text)
        assert result.is_toxic, text
        assert "sexual" in result.categories, text

    def test_sala_is_an_insult_not_a_slur(self, bn):
        # শালা/সালা literally means brother-in-law and is everyday idiom, so
        # it masks rather than blocks — the same call made for Hindi साला.
        result = bn.analyze("তুই সালা")
        assert result.is_toxic
        assert "insult" in result.categories
        assert result.severity is not Severity.CRITICAL

    def test_colloquial_spelling_matches_standard_spelling(self, bn):
        assert bn.analyze("সালা").is_toxic == bn.analyze("শালা").is_toxic

    @pytest.mark.parametrize("text", [
        "আমি ভাত খাই",
        "তুমি কেমন আছো",
        "আমার বোন স্কুলে যায়",
        "আমার মায়ের হাতের রান্না খুব ভালো",
    ])
    def test_ordinary_bengali_stays_clean(self, bn, text):
        assert not bn.analyze(text).is_toxic, text


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


class TestAllLanguagesCategorised:
    """
    The policy layer only works if every pack declares categories — otherwise
    a slur in Russian or Korean silently degrades to plain profanity.
    """

    def test_every_pack_declares_categories(self):
        from lpte.languages import (
            ArabicProfile, BengaliProfile, ChineseProfile, EnglishProfile,
            FrenchProfile, GermanProfile, HindiProfile, JapaneseProfile,
            KoreanProfile, RussianProfile, SpanishProfile,
        )
        packs = {
            "en": EnglishProfile, "bn": BengaliProfile, "ru": RussianProfile,
            "zh": ChineseProfile, "ja": JapaneseProfile, "ko": KoreanProfile,
            "es": SpanishProfile, "hi": HindiProfile, "fr": FrenchProfile,
            "de": GermanProfile, "ar": ArabicProfile,
        }
        for code, profile in packs.items():
            assert len(profile.word_categories) > 0, (
                f"{code} has no word_categories — slurs/threats won't escalate"
            )

    def test_no_category_key_is_unknown(self):
        """Guards against typos in non-Latin scripts silently doing nothing."""
        from lpte.languages import (
            ArabicProfile, BengaliProfile, ChineseProfile, EnglishProfile,
            FrenchProfile, GermanProfile, HindiProfile, JapaneseProfile,
            KoreanProfile, RussianProfile, SpanishProfile,
        )
        packs = {
            "en": EnglishProfile, "bn": BengaliProfile, "ru": RussianProfile,
            "zh": ChineseProfile, "ja": JapaneseProfile, "ko": KoreanProfile,
            "es": SpanishProfile, "hi": HindiProfile, "fr": FrenchProfile,
            "de": GermanProfile, "ar": ArabicProfile,
        }
        for code, profile in packs.items():
            unknown = [w for w in profile.word_categories if w not in profile.bad_words]
            assert not unknown, f"{code}: category keys not in vocabulary: {unknown}"

    @pytest.mark.parametrize("code,text,category", [
        ("ru", "пидор", "slur"),
        ("zh", "婊子", "slur"),
        ("ja", "死ね", "threat"),
        ("ko", "병신", "slur"),
        ("es", "puta marica", "slur"),
        ("hi", "हिजड़ा", "slur"),
        ("fr", "négre salope", "slur"),
        ("de", "neger schwuchtel", "slur"),
        ("ar", "شرموطة", "slur"),
    ])
    def test_slurs_escalate_in_every_language(self, code, text, category):
        from lpte.languages import (
            ArabicProfile, ChineseProfile, FrenchProfile, GermanProfile,
            HindiProfile, JapaneseProfile, KoreanProfile, RussianProfile,
            SpanishProfile,
        )
        packs = {
            "ru": RussianProfile, "zh": ChineseProfile, "ja": JapaneseProfile,
            "ko": KoreanProfile, "es": SpanishProfile, "hi": HindiProfile,
            "fr": FrenchProfile, "de": GermanProfile, "ar": ArabicProfile,
        }
        engine = LpteEngine(packs[code], cache_size=0)
        result = engine.analyze(text)
        assert category in result.categories, f"{code}: {text}"
        assert result.severity == Severity.CRITICAL, f"{code}: {text} did not escalate"


class TestReclaimedAndAmbiguousTerms:
    """
    Words that are legitimately used by the community they describe must not
    be hard-blocked — that censors the very people moderation should protect.
    """

    @pytest.mark.parametrize("text", [
        "the queer community centre",
        "queer studies course",
        "queer rights are human rights",
        "queer history month",
    ])
    def test_reclaimed_queer_usage_allowed(self, en, text):
        assert not en.analyze(text).is_toxic, text

    def test_abusive_queer_usage_still_flagged(self, en):
        result = en.analyze("you are such a queer")
        assert result.is_toxic
        # detectable, but masked rather than hard-blocked
        assert result.severity == Severity.HIGH
        assert "slur" not in result.categories

    def test_unambiguous_slurs_still_blocked(self, en):
        from lpte.core.policy import Action, policy_balanced
        policy = policy_balanced()
        for text in ["you nigger", "you faggot", "you tranny", "you retard"]:
            assert policy.decide(en.analyze(text)).action == Action.BLOCK, text


class TestDeterminism:
    def test_matched_terms_order_is_stable(self, en):
        """Set iteration must never leak into output ordering."""
        first = en.analyze("you stupid nigger idiot").matched_terms
        for _ in range(20):
            assert en.analyze("you stupid nigger idiot").matched_terms == first
