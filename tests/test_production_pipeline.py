"""End-to-end regression tests for masking, pack rules and code switching."""

import asyncio
import json
from pathlib import Path

import pytest

from lpte import LanguagePackLoader, LpteEngine, MultiLangEngine
from lpte.core.normalizer import TextNormalizer
from lpte.languages import (
    ArabicProfile, BengaliProfile, ChineseProfile, EnglishProfile, JapaneseProfile,
)
from lpte.registry import available_languages, builtin_profiles


@pytest.mark.parametrize("surface,masked", [
    ("f4ck", "****"),
    ("f.u.c.k", "*******"),
    ("f-u-c-k", "*******"),
    ("f u c k", "*******"),
    ("f\u200bu\u200bck", "******"),
    ("shiiit", "******"),
    ("f@ck1ng", "*******"),
    ("fcking", "******"),
    ("phuck", "*****"),
    ("bstrd", "*****"),
    ("ass!", "***!"),
])
def test_masks_original_obfuscated_spans(surface, masked):
    engine = LpteEngine(EnglishProfile)
    assert engine.sanitize(surface) == masked
    assert engine.sanitize(f"hello {surface} world", mask="#") == (
        f"hello {masked.replace('*', '#')} world"
    )


def test_mask_only_matched_occurrences_and_preserve_unmatched_words():
    engine = LpteEngine(EnglishProfile)
    text = "class ass! please kill the background process, f4ck"
    assert engine.sanitize(text) == "class ***! please kill the background process, ****"
    assert engine.sanitize("damn damn") == "**** ****"
    assert engine.sanitize("hello world") == "hello world"
    with pytest.raises(ValueError):
        engine.sanitize("damn", mask="***")


def test_context_rules_cover_only_this_occurrence():
    ja = LpteEngine(JapaneseProfile)
    text = "美味しい豚肉を食べました 豚"
    assert ja.analyze(text).is_toxic
    assert ja.sanitize(text) == "美味しい豚肉を食べました *"
    zh = LpteEngine(ChineseProfile)
    assert zh.sanitize("草地の草") == "草地の*"
    en = LpteEngine(EnglishProfile)
    assert en.is_toxic("I passed the exam. you ass!")


def test_no_identity_or_literal_dog_flags():
    assert not LpteEngine(BengaliProfile).is_toxic("আমার মায়ের দুধ দিয়ে চা, হিন্দু বন্ধু")
    assert not LpteEngine(ArabicProfile).is_toxic("هذا كلب بوليسي")
    assert not LpteEngine(JapaneseProfile).is_toxic("障害者の権利を守る")


def test_multilingual_routes_only_applicable_scripts(monkeypatch):
    engine = MultiLangEngine([BengaliProfile, EnglishProfile], cache_size=0)

    def unexpected(*_args):
        raise AssertionError("English pack should not run on pure Bengali")

    monkeypatch.setattr(engine.engines["en"], "analyze", unexpected)
    assert engine.analyze("কুত্তা").language == "bn"
    assert engine.sanitize("কুত্তা") == "******"


def test_multilingual_combines_categories_without_masking_clean_context():
    engine = MultiLangEngine([BengaliProfile, EnglishProfile])
    text = "কুত্তা idiot আমি বাংলায় কথা বলি"
    result = engine.analyze(text)
    assert result.is_toxic
    assert result.language == "bn+en"
    assert result.matched_terms == ["কুত্তা", "idiot"]
    assert engine.sanitize(text) == "****** ***** আমি বাংলায় কথা বলি"
    assert not engine.analyze("আমি বাংলায় কথা বলি").is_toxic


def test_mixed_language_cache_and_policy_do_not_double_count_matches():
    from lpte import get_policy

    engine = MultiLangEngine([BengaliProfile, EnglishProfile])
    high = engine.analyze("কুত্তা and idiot", threshold=.9)
    assert not high.is_toxic
    high.matched_terms.clear()
    low = engine.analyze("কুত্তা and idiot", threshold=.6)
    assert low.is_toxic and low.matched_terms == ["কুত্তা", "idiot"]
    # Two exact matches in separate engines do not inflate one pack's .8
    # confidence into 1.0 when a moderation policy is applied.
    assert low.confidence == get_policy("balanced").decide(low).confidence == .8


def test_cached_evidence_is_threshold_free_and_not_shared():
    engine = LpteEngine(EnglishProfile, cache_size=2)
    r = engine.analyze("damn", threshold=.9)
    assert not r.is_toxic and r.confidence == .8
    r.matched_terms.clear()
    r.signals.clear()
    r.categories.clear()
    again = engine.analyze("damn", threshold=.6)
    assert again.is_toxic and again.matched_terms == ["damn"]
    assert again.categories == ["profanity"]
    assert again.signals["exact_match"] == 1
    assert engine.cache_stats()["hits"] == 1
    assert not engine.analyze("hello", threshold=0).is_toxic
    for value in (-.1, 1.1, float("nan"), float("inf")):
        with pytest.raises(ValueError):
            engine.analyze("damn", threshold=value)


def test_async_and_html_no_double_decoding():
    engine = LpteEngine(EnglishProfile)

    async def run():
        assert (await engine.analyze_async("f4ck")).is_toxic
        results = await engine.batch_analyze_async(["hello", "ass!"])
        assert [r.is_toxic for r in results] == [False, True]

    asyncio.run(run())
    assert engine.analyze_html("<b>hello</b> &#102;uck").is_toxic
    # '&amp;#102;' decodes once into literal '&#102;', not into the letter f.
    assert not engine.analyze_html("&amp;#102;uck").is_toxic


def test_clean_numeric_ids_do_not_trigger_extra_normalization_passes():
    norm = TextNormalizer()
    assert len(norm.normalize_with_alternatives("word4 word111 word42")) == 1
    assert len(norm.normalize_with_alternatives("f4ck")) == 2
    assert len(norm.normalize_with_alternatives("shiiit")) == 2


def test_normalized_spans_match_fast_path():
    norm = TextNormalizer()
    assert norm.normalize("con\u0303o") == norm.normalize("coño") == "coño"
    for text in ("f4ck", "sh!t", "ass!", "f\u200bu.c.k", "shiiit", "f@ck1ng",
                 "তুই একদম idiot", "美味しい豚肉", "!", "naïve", "İçin"):
        variants = norm.normalize_with_alternatives(text)
        mapped = norm.normalize_variants_with_spans(text)
        assert variants == [v.text for v in mapped], text
        assert all(len(v.text) == len(v.offsets) for v in mapped)
        for variant in mapped:
            assert all(0 <= a <= b <= len(text) for a, b in variant.offsets)


def test_json_packs_share_lexicon_and_categories_with_builtins():
    profiles = LanguagePackLoader.load_directory(Path(__file__).parent.parent / "languages")
    for code, builtin in builtin_profiles().items():
        pack = profiles[code]
        assert pack.bad_words == builtin.bad_words
        assert pack.word_categories == builtin.word_categories
        assert pack.aliases == builtin.aliases
        assert pack.context_rules == builtin.context_rules


def test_new_data_only_pack_aliases_categories_scripts_and_suffixes(tmp_path):
    pack = {
        "language_code": "xx", "language_name": "Test tongue",
        "bad_words": ["badword", "go away"],
        "word_categories": {"badword": "insult", "go away": "threat"},
        "aliases": {"bwd": "badword"}, "suffix_rules": ["s"],
        "context_rules": {"badword": ["badwordsafe"]}, "scripts": ["Latin"],
    }
    file = tmp_path / "xx_profile.json"
    file.write_text(json.dumps(pack), encoding="utf-8")
    loaded = available_languages(tmp_path)
    engine = MultiLangEngine([loaded["xx"], EnglishProfile])
    assert engine.analyze("bwd").categories == ["insult"]
    assert engine.analyze("go away").categories == ["threat"]
    assert LpteEngine(loaded["xx"]).is_toxic("badwords")
    assert LpteEngine(loaded["xx"]).sanitize("bwd") == "***"
    assert loaded["xx"].stemmer.stem("badwords") == "badword"


@pytest.mark.parametrize("patch,expected", [
    ({"bad_words": "word"}, "bad_words"),
    ({"bad_words": ["word", "word"]}, "duplicate"),
    ({"word_categories": {"word": "danger"}}, "word_categories"),
    ({"word_categories": {"typo": "threat"}}, "not in bad_words"),
    ({"aliases": {"variant": "typo"}}, "alias"),
    ({"suffix_rules": [5]}, "suffix_rules"),
    ({"context_rules": {"word": "not a list"}}, "context_rules"),
    ({"scripts": ["Imaginary"]}, "unknown scripts"),
    ({"min_word_length": True}, "positive integer"),
    ({"bad_wrods": ["word"]}, "unknown field"),
    ({"bad_words": ["w0rd"]}, "not normalized; use 'word'"),
    ({"bad_words": ["!word"]}, "not normalized"),
    ({"aliases": {"v4riant": "word"}}, "not normalized"),
    ({"aliases": {"variant": []}}, "alias"),
    ({"context_rules": {"word": ["word!"]}}, "not normalized"),
    ({5: "bad"}, "keys must be strings"),
])
def test_pack_validation_has_field_specific_errors(patch, expected):
    data = {"language_code": "xx", "language_name": "Test", "bad_words": ["word"]}
    data.update(patch)
    with pytest.raises(ValueError, match=expected):
        LanguagePackLoader.load_dict(data)


def test_fuzzy_lookup_does_not_scan_the_entire_vocabulary(monkeypatch):
    import string

    import lpte.core.classifier as module
    from lpte.core.classifier import Classifier
    from lpte.core.loader import SuffixStripper
    from lpte.core.profile import LanguageProfile
    from lpte.core.tokenizer import Tokenizer

    words = {f"zzzz{a}{b}{c}" for a in string.ascii_lowercase
             for b in string.ascii_lowercase for c in "abc"}
    profile = LanguageProfile("xx", "Synthetic", words, SuffixStripper([]))
    classifier = Classifier(profile)
    calls = []
    original = module._edit_distance_1

    def count(*args):
        calls.append(1)
        return original(*args)

    monkeypatch.setattr(module, "_edit_distance_1", count)
    result = classifier.classify(Tokenizer().tokenize("welcome friend"), profile)
    assert not result.is_toxic
    assert len(calls) < 10  # old linear fuzzy search visited thousands


def test_invalid_pack_is_not_silently_ignored(tmp_path):
    (tmp_path / "xx_profile.json").write_text("{}")
    with pytest.raises(ValueError, match="missing required"):
        available_languages(tmp_path)
