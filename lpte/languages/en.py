"""English language pack — stemmer, profile, and dictionary."""

from lpte.core.profile import LanguageProfile
from lpte.core.stemmer import Stemmer


class EnglishStemmer(Stemmer):
    """
    English language stemmer — simplified suffix stripping.

    Handles common inflections:
    - Plurals: -s, -es, -ies
    - Past tense: -ed, -ied
    - Progressive: -ing
    - Comparative: -er, -est
    - Derivational: -tion, -ness, -ment, -able
    - Double-consonant forms: -pping → -p (e.g., shitting → shit)

    Lightweight — prioritizes recall (catching all toxic forms) over precision.
    """

    SUFFIXES = sorted(
        [
            # Long suffixes first
            "ification", "fulness", "ousness", "iveness",
            "ation", "ition", "ness", "ment", "able", "ible",
            "tion", "sion", "ence", "ance",
            # Verb endings
            "ating", "izing", "ifying", "ening",
            "ing", "ied", "ies",
            # Adjective/adverb
            "ful", "less", "ous", "ive", "ial", "ual",
            "ly", "er", "est",
            # Plurals and past
            "sses", "shes", "ches", "xes", "zes",
            "ves",
            "ed", "es", "s",
        ],
        key=len,
        reverse=True,
    )

    # Doubled consonants that may appear before -ing/-ed (e.g., fucking → fuck)
    _DOUBLE_CONSONANTS = set("bcdfghjklmnpqrstvwxyz")

    MIN_STEM_LENGTH = 3

    # Suffixes bucketed by their final character. SUFFIXES is sorted longest
    # first, and each bucket preserves that relative order, so candidate
    # iteration is semantically identical to scanning SUFFIXES directly while
    # checking only the handful of suffixes that could possibly match.
    _SUFFIX_BY_LAST: dict[str, tuple[str, ...]] = {}

    def stem(self, word: str) -> str:
        if len(word) < self.MIN_STEM_LENGTH + 2:
            return word

        for suffix in self._SUFFIX_BY_LAST.get(word[-1], ()):
            if word.endswith(suffix) and len(word) - len(suffix) >= self.MIN_STEM_LENGTH:
                stemmed = word[: -len(suffix)]
                # Restore 'y' after dropping 'ied'/'ies'
                if suffix in ("ied", "ies"):
                    return stemmed + "y"
                # Handle doubled consonant before -ing/-ed (e.g., "shitting" → "shit")
                if (
                    suffix in ("ing", "ed")
                    and len(stemmed) >= 2
                    and stemmed[-1] == stemmed[-2]
                    and stemmed[-1] in self._DOUBLE_CONSONANTS
                ):
                    return stemmed[:-1]
                return stemmed

        return word


# ─── English Profanity Dictionary ─────────────────────────────────────────────
# Root forms only — inflections are handled by the stemmer.
_ENGLISH_BAD_WORDS: set[str] = {
    # ── General profanity ──────────────────────────────────────────────────────
    "fuck", "shit", "ass", "asshole", "bastard", "damn",
    "hell", "crap", "piss", "dick", "cock", "pussy", "tits",
    "bitch", "whore", "slut", "cunt", "twat", "wank", "wanker",
    "arse", "bollocks", "bugger", "prick", "tosser", "idiot",
    "moron", "imbecile", "dumbass", "dumbfuck", "fuckface",
    "fuckwit", "dipshit", "jackass", "shithead", "asshat",
    "numbskull", "douchebag", "douche",

    # ── Slurs — racial/ethnic ──────────────────────────────────────────────────
    "nigger", "nigga", "spic", "chink", "kike", "wetback",
    "cracker", "honky", "gook", "towelhead", "sandnigger",
    "beaner", "redskin", "raghead", "zipperhead", "coon",
    "darkie", "jungle bunny", "porch monkey",

    # ── Slurs — gender/sexuality ───────────────────────────────────────────────
    "faggot", "fag", "dyke", "homo", "queer",
    "tranny", "shemale", "ladyboy",

    # ── Slurs — disability ────────────────────────────────────────────────────
    "retard", "retarded", "cripple", "spastic", "tard",
    "moron", "idiot", "imbecile",

    # ── Severe / compound ─────────────────────────────────────────────────────
    "motherfucker", "cocksucker", "bullshit", "horseshit",
    "clusterfuck", "mindfuck", "fuckup", "shitfaced",
    "shitstorm", "asswipe", "butthead",

    # ── Threats / harassment ──────────────────────────────────────────────────
    # NOTE: bare "kill" is deliberately NOT listed — it is ordinary vocabulary
    # in tech and gaming ("kill the process", "kill switch", "kill the boss").
    # Only violence directed at a person is treated as a threat.
    "kill yourself", "kys", "go die", "kill you", "kill your self",
    "kill him", "kill her", "kill them", "kill us", "kill everyone",
    "kill everyone", "will kill", "gonna kill", "going to kill",
    "murder", "murder you",
    "rape", "rapist", "pedophile", "pedo", "groomer",

    # ── Vowel-dropped / deliberate misspellings ───────────────────────────────
    # Dropping vowels is a standard evasion trick ("fcking", "bstrd"). These
    # are listed explicitly rather than by stripping vowels at runtime, because
    # blanket vowel-stripping collides catastrophically with ordinary words
    # (count → cnt → cunt, bass → bss → ass). None of the strings below are
    # real words in any language, so they carry no false-positive risk.
    "fck", "fcking", "fckn", "fkn", "fuk", "fuking", "fukk",
    "phuck", "phuk", "phucking",
    "bstrd", "mthrfcker", "mthrfkr", "btch", "biatch",
    "a$$", "azz", "shyt", "wh0re",

    # ── Bullying / personal attacks (the most common real-world reports) ──────
    # Categorised as "insult" (non-escalating): hurtful, but not the same harm
    # class as a slur or a threat, so policies can mask instead of block.
    "stupid", "idiotic", "ugly", "loser", "pathetic",
    "worthless", "useless", "disgusting", "scum", "trash",
    "garbage", "freak", "weirdo", "creep", "shut up",
    "nobody likes you", "kill yourself", "kys",
    "stfu", "gtfo",
}

# ─── Content Categories ───────────────────────────────────────────────────────
# Categories let consumers apply different actions per harm type — the same
# confidence means different things for "damn" vs a racial slur vs a death
# threat. Slur/threat matches escalate one severity level in the classifier.
# Anything not listed defaults to "profanity".
_ENGLISH_WORD_CATEGORIES: dict[str, str] = {
    # Identity-based slurs — highest harm, escalate + never allow
    **{w: "slur" for w in (
        "nigger", "nigga", "spic", "chink", "kike", "wetback", "cracker",
        "honky", "gook", "towelhead", "sandnigger", "beaner", "redskin",
        "raghead", "zipperhead", "coon", "darkie", "jungle bunny",
        "porch monkey", "faggot", "fag", "dyke", "homo",
        "tranny", "shemale", "ladyboy", "retard", "retarded", "cripple",
        "spastic", "tard", "whore", "slut", "cunt",
    )},
    # Violence, self-harm incitement, sexual violence — escalate
    **{w: "threat" for w in (
        "kill yourself", "kys", "go die", "kill you", "kill your self",
        "kill him", "kill her", "kill them", "kill us", "kill everyone",
        "will kill", "gonna kill", "going to kill", "murder", "murder you",
        "rape", "rapist", "pedophile", "pedo", "groomer",
    )},
    # Sexually explicit / degrading
    **{w: "sexual" for w in (
        "cock", "cocksucker", "pussy", "tits", "dick", "wank", "wanker",
    )},
    # Bullying / personal attacks — hurtful, but a lower harm class than
    # slurs or threats, so policies mask rather than block these.
    **{w: "insult" for w in (
        "stupid", "idiotic", "ugly", "loser", "pathetic", "worthless",
        "useless", "disgusting", "scum", "trash", "garbage", "freak",
        "weirdo", "creep", "shut up", "nobody likes you",
        "stfu", "gtfo",
        # Reclaimed / ambiguous: detectable, but masked rather than blocked.
        "queer",
    )},
}

EnglishProfile = LanguageProfile(
    language_code="en",
    language_name="English",
    bad_words=_ENGLISH_BAD_WORDS,
    stemmer=EnglishStemmer(),
    word_categories=_ENGLISH_WORD_CATEGORIES,
    context_rules={
        "ass":    {"class", "grass", "bass", "brass", "mass", "pass", "lass", "sass", "crass"},
        "hell":   {"hello", "shell", "hellen", "helo", "dwell", "belle"},
        "dick":   {"dickens", "richard", "dictionary"},
        "cock":   {"cockney", "peacock", "cockatoo", "cockerel", "hancock"},
        "prick":  {"prickle", "lipstick"},
        "crap":   {"crapper", "crappy"},
        "bitch":  {"bitchy"},
        "queer":  {"queerly", "queer community", "queer studies",
                   "queer theory", "queer rights", "queer people",
                   "queer youth", "queer identity", "queer cinema",
                   "queer literary", "queer history"},
        "kys":    set(),   # no safe variants — always flag
        # Everyday nouns that double as insults. The classifier only allows
        # these when the word's occurrence sits inside the benign collocation,
        # so "you are trash" is still flagged.
        "trash": {
            "trash can", "trash bin", "trash bag", "trash collection",
            "take out the trash", "trash pickup",
        },
        "garbage": {
            "garbage can", "garbage truck", "garbage bag",
            "garbage collection", "garbage disposal",
        },
    },
    min_word_length=2,
    version="1.1.0",
    description="English profanity and toxicity word list with stemmer",
    author="LPTE Contributors",
)


# Build the last-character suffix index (ordered longest-first within buckets).
for _suffix in EnglishStemmer.SUFFIXES:
    EnglishStemmer._SUFFIX_BY_LAST.setdefault(_suffix[-1], []).append(_suffix)
EnglishStemmer._SUFFIX_BY_LAST = {
    _k: tuple(_v) for _k, _v in EnglishStemmer._SUFFIX_BY_LAST.items()
}
