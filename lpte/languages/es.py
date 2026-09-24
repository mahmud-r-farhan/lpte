"""Spanish language pack — stemmer, profile, and dictionary."""

from lpte.core.profile import LanguageProfile
from lpte.core.stemmer import Stemmer


class SpanishStemmer(Stemmer):
    """
    Spanish language stemmer — suffix stripping for verbs, nouns, adjectives.
    """

    SUFFIXES = sorted(
        [
            # Diminutives and superlatives
            "isimo", "isima", "isimos", "isimas",
            "isimamente", "osamente", "icamente",
            "mente", "amiento", "imiento",
            # Participles and gerunds
            "ando", "iendo", "yendo", "ado", "ido", "ada", "ida",
            "ados", "idos", "adas", "idas",
            # Noun and adjective suffixes
            "ciones", "siones", "cion", "sion", "idades", "idad",
            "oso", "osa", "osos", "osas",
            "ito", "ita", "itos", "itas",
            "uelo", "uela", "uelos", "uelas",
            # Plurals
            "es", "s",
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


_SPANISH_BAD_WORDS: set[str] = {
    "puta", "puto", "putas", "putos", "puton", "putona",
    "mierda", "mierdas", "mierdoso", "mierdosa",
    "joder", "jodete", "jodido", "jodida", "jodidos",
    "coño", "coños", "pendejo", "pendeja", "pendejos", "pendejas",
    "cabron", "cabrona", "cabrones", "cabronas",
    "chinga", "chingada", "chingado", "chingar", "chingados",
    "estupido", "estupida", "estupidos", "estupidas",
    "idiota", "idiotas", "imbecil", "imbeciles",
    "maldito", "maldita", "malditos", "malditas",
    "hijueputa", "hijadeputa", "hijodeputa", "hdp",
    "marica", "maricon", "maricones", "culero", "culera",
    "verga", "culo", "picha", "cipote", "gilipollas",
    "mamaguevo", "mamabicho", "careverga", "gonorrea",
    "zorra", "perra", "bastardo", "bastarda",
}

# ─── Content Categories ───────────────────────────────────────────────────────
# Slurs and threats escalate severity; profanity is the default.
_SPANISH_WORD_CATEGORIES: dict[str, str] = {
    **{w: "slur" for w in (
        "puta", "puto", "putas", "putos", "puton", "putona",
        "zorra", "perra", "bastardo", "bastarda", "marica", "maricon",
        "maricones", "gonorrea",
    )},
    **{w: "sexual" for w in (
        "coño", "coños", "chinga", "chingada", "chingado", "chingar",
        "chingados", "verga", "culo", "picha", "cipote", "culero",
        "culera",
    )},
    **{w: "insult" for w in (
        "pendejo", "pendeja", "pendejos", "pendejas", "estupido", "estupida",
        "estupidos", "estupidas", "idiota", "idiotas", "imbecil", "imbeciles",
        "gilipollas", "mamaguevo", "mamabicho", "careverga", "maldito", "maldita",
        "malditos", "malditas",
    )},
}

SpanishProfile = LanguageProfile(
    language_code="es",
    language_name="Español (Spanish)",
    bad_words=_SPANISH_BAD_WORDS,
    stemmer=SpanishStemmer(),
    word_categories=_SPANISH_WORD_CATEGORIES,
    context_rules={},
    min_word_length=2,
    version="1.1.0",
    description="Spanish profanity and toxicity word list with inflectional stemmer",
    author="LPTE Contributors",
)
