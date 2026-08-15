"""Comprehensive tests for all language profiles and stemmers (EN, BN, ZH, JA, KO, RU, ES, HI, FR, DE, AR)."""

from pathlib import Path
import pytest

from lpte.core.engine import LpteEngine
from lpte.core.loader import LanguagePackLoader
from lpte.languages.ar import ArabicProfile, ArabicStemmer
from lpte.languages.bn import BengaliProfile, BengaliStemmer
from lpte.languages.de import GermanProfile, GermanStemmer
from lpte.languages.en import EnglishProfile, EnglishStemmer
from lpte.languages.es import SpanishProfile, SpanishStemmer
from lpte.languages.fr import FrenchProfile, FrenchStemmer
from lpte.languages.hi import HindiProfile, HindiStemmer
from lpte.languages.ja import JapaneseProfile, JapaneseStemmer
from lpte.languages.ko import KoreanProfile, KoreanStemmer
from lpte.languages.ru import RussianProfile, RussianStemmer
from lpte.languages.zh import ChineseProfile, ChineseStemmer


class TestChinese:
    @pytest.fixture
    def engine(self):
        return LpteEngine(ChineseProfile)

    def test_detects_chinese_profanity(self, engine):
        result = engine.analyze("你这个傻逼")
        assert result.is_toxic

    def test_detects_chinese_compound(self, engine):
        result = engine.analyze("草泥马")
        assert result.is_toxic

    def test_chinese_clean_sentence(self, engine):
        result = engine.analyze("你好，今天的天气真好，我们去散步吧")
        assert not result.is_toxic

    def test_chinese_stemmer_particles(self):
        stemmer = ChineseStemmer()
        assert stemmer.stem("傻逼们") == "傻逼"
        assert stemmer.stem("混蛋的") == "混蛋"


class TestJapanese:
    @pytest.fixture
    def engine(self):
        return LpteEngine(JapaneseProfile)

    def test_detects_japanese_profanity(self, engine):
        result = engine.analyze("死ね くそ野郎")
        assert result.is_toxic

    def test_detects_japanese_insult(self, engine):
        result = engine.analyze("あいつは本当にバカですね")
        assert result.is_toxic

    def test_japanese_clean_sentence(self, engine):
        result = engine.analyze("こんにちは！今日はとても良い天気ですね。")
        assert not result.is_toxic

    def test_japanese_context_rule_pork(self, engine):
        # 豚肉 (pork) should be clean
        result = engine.analyze("美味しい豚肉を食べました")
        assert not result.is_toxic

    def test_japanese_stemmer(self):
        stemmer = JapaneseStemmer()
        assert stemmer.stem("死ねでした") == "死ね"
        assert stemmer.stem("バカたち") == "バカ"


class TestKorean:
    @pytest.fixture
    def engine(self):
        return LpteEngine(KoreanProfile)

    def test_detects_korean_profanity(self, engine):
        result = engine.analyze("야 이 씨발 개새끼야")
        assert result.is_toxic

    def test_detects_korean_slur(self, engine):
        result = engine.analyze("닥쳐 병신새끼야")
        assert result.is_toxic

    def test_korean_clean_sentence(self, engine):
        result = engine.analyze("안녕하세요! 오늘 날씨가 참 좋습니다.")
        assert not result.is_toxic

    def test_korean_context_rule_trashcan(self, engine):
        # 쓰레기통 (trash can) should be clean
        result = engine.analyze("방에 쓰레기통을 두었습니다")
        assert not result.is_toxic

    def test_korean_stemmer_josa_eomi(self):
        stemmer = KoreanStemmer()
        assert stemmer.stem("새끼에게") == "새끼"
        assert stemmer.stem("병신입니다") == "병신"


class TestRussian:
    @pytest.fixture
    def engine(self):
        return LpteEngine(RussianProfile)

    def test_detects_russian_mat(self, engine):
        result = engine.analyze("ты сука иди нахуй")
        assert result.is_toxic

    def test_detects_inflected_russian(self, engine):
        result = engine.analyze("заебали эти мудаки")
        assert result.is_toxic

    def test_russian_clean_sentence(self, engine):
        result = engine.analyze("Привет! Как твои дела и работа?")
        assert not result.is_toxic

    def test_russian_stemmer_inflections(self):
        stemmer = RussianStemmer()
        assert stemmer.stem("мудаками") == "мудак"


class TestSpanish:
    @pytest.fixture
    def engine(self):
        return LpteEngine(SpanishProfile)

    def test_detects_spanish_profanity(self, engine):
        result = engine.analyze("eres un pendejo de mierda")
        assert result.is_toxic

    def test_spanish_clean_sentence(self, engine):
        result = engine.analyze("Hola amigo, ¿cómo estás hoy en la casa?")
        assert not result.is_toxic


class TestHindi:
    @pytest.fixture
    def engine(self):
        return LpteEngine(HindiProfile)

    def test_detects_hindi_profanity(self, engine):
        result = engine.analyze("तू बड़ा कमीना और हरामी है")
        assert result.is_toxic

    def test_hindi_clean_sentence(self, engine):
        result = engine.analyze("नमस्ते दोस्त, आज का मौसम बहुत अच्छा है")
        assert not result.is_toxic


class TestFrench:
    @pytest.fixture
    def engine(self):
        return LpteEngine(FrenchProfile)

    def test_detects_french_profanity(self, engine):
        result = engine.analyze("ferme ta gueule espèce de connard")
        assert result.is_toxic

    def test_french_clean_sentence(self, engine):
        result = engine.analyze("Bonjour monsieur, comment allez-vous aujourd'hui?")
        assert not result.is_toxic


class TestGerman:
    @pytest.fixture
    def engine(self):
        return LpteEngine(GermanProfile)

    def test_detects_german_profanity(self, engine):
        result = engine.analyze("du verdammtes arschloch")
        assert result.is_toxic

    def test_german_clean_sentence(self, engine):
        result = engine.analyze("Guten Tag, das Wetter ist heute wirklich schön")
        assert not result.is_toxic


class TestArabic:
    @pytest.fixture
    def engine(self):
        return LpteEngine(ArabicProfile)

    def test_detects_arabic_profanity(self, engine):
        result = engine.analyze("يا ابن الكلب يا سافل")
        assert result.is_toxic

    def test_arabic_clean_sentence(self, engine):
        result = engine.analyze("السلام عليكم ورحمة الله وبركاته كيف حالك اليوم")
        assert not result.is_toxic


class TestAllJsonPacksLoadable:
    def test_load_all_json_profiles(self):
        langs_dir = Path(__file__).parent.parent / "languages"
        packs = LanguagePackLoader.load_directory(langs_dir)

        expected_codes = {"en", "bn", "zh", "ja", "ko", "ru", "es", "hi", "fr", "de", "ar"}
        assert expected_codes.issubset(packs.keys()), f"Missing packs in {set(packs.keys())}"

        for code, profile in packs.items():
            assert len(profile.bad_words) > 0, f"Empty dictionary for {code}"
            assert profile.stemmer is not None, f"Missing stemmer for {code}"
            engine = LpteEngine(profile)
            assert isinstance(engine, LpteEngine)
