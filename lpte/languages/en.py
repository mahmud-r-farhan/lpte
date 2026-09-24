"""English language pack — stemmer, profile, and dictionary."""

from lpte.core.profile import LanguageProfile
from lpte.core.stemmer import Stemmer
from lpte.languages.categories import categories_for


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
            "ification",
            "fulness",
            "ousness",
            "iveness",
            "ation",
            "ition",
            "ness",
            "ment",
            "able",
            "ible",
            "tion",
            "sion",
            "ence",
            "ance",
            # Verb endings
            "ating",
            "izing",
            "ifying",
            "ening",
            "ing",
            "ied",
            "ies",
            # Adjective/adverb
            "ful",
            "less",
            "ous",
            "ive",
            "ial",
            "ual",
            "ly",
            "er",
            "est",
            # Plurals and past
            "sses",
            "shes",
            "ches",
            "xes",
            "zes",
            "ves",
            "ed",
            "es",
            "s",
        ],
        key=len,
        reverse=True,
    )

    # Doubled consonants that may appear before -ing/-ed (e.g., fucking → fuck)
    _DOUBLE_CONSONANTS = set("bcdfghjklmnpqrstvwxyz")

    MIN_STEM_LENGTH = 3

    def stem(self, word: str) -> str:
        if len(word) < self.MIN_STEM_LENGTH + 2:
            return word

        for suffix in self.SUFFIXES:
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
    "fuck",
    "shit",
    "ass",
    "asshole",
    "bastard",
    "damn",
    "hell",
    "crap",
    "piss",
    "dick",
    "cock",
    "pussy",
    "tits",
    "bitch",
    "whore",
    "slut",
    "cunt",
    "twat",
    "wank",
    "wanker",
    "arse",
    "bollocks",
    "bugger",
    "prick",
    "tosser",
    "idiot",
    "moron",
    "imbecile",
    "dumbass",
    "dumbfuck",
    "fuckface",
    "fuckwit",
    "dipshit",
    "jackass",
    "shithead",
    "asshat",
    "numbskull",
    "douchebag",
    "douche",
    # ── Slurs — racial/ethnic ──────────────────────────────────────────────────
    "nigger",
    "nigga",
    "spic",
    "chink",
    "kike",
    "wetback",
    "cracker",
    "honky",
    "gook",
    "towelhead",
    "sandnigger",
    "beaner",
    "redskin",
    "raghead",
    "zipperhead",
    "coon",
    "darkie",
    "jungle bunny",
    "porch monkey",
    # ── Slurs — gender/sexuality ───────────────────────────────────────────────
    "faggot",
    "fag",
    "dyke",
    "homo",
    "tranny",
    "shemale",
    "ladyboy",
    # ── Slurs — disability ────────────────────────────────────────────────────
    "retard",
    "retarded",
    "cripple",
    "spastic",
    "tard",
    # ── Severe / compound ─────────────────────────────────────────────────────
    "motherfucker",
    "cocksucker",
    "bullshit",
    "horseshit",
    "clusterfuck",
    "mindfuck",
    "fuckup",
    "shitfaced",
    "shitstorm",
    "asswipe",
    "butthead",
    # ── Threats / harassment ──────────────────────────────────────────────────
    # Targeted phrases, not ambiguous bare words such as 'kill' or 'murder'.
    "kill yourself",
    "kys",
    "go die",
    "kill you",
    "kill him",
    "kill her",
    "kill them",
    "i will kill you",
    "i will hurt you",
    "i will rape you",
    # Targeted bullying without labelling every use of 'stupid' or 'ugly'.
    "you are stupid",
    "you are so stupid",
    "you are ugly",
}

EnglishProfile = LanguageProfile(
    language_code="en",
    language_name="English",
    bad_words=_ENGLISH_BAD_WORDS,
    stemmer=EnglishStemmer(),
    word_categories=categories_for("en", _ENGLISH_BAD_WORDS),
    aliases={"fck": "fuck", "fcking": "fuck", "bstrd": "bastard", "phuck": "fuck"},
    context_rules={
        "ass": {"class", "grass", "bass", "brass", "mass", "pass", "lass", "sass", "crass"},
        "hell": {"hello", "shell", "hellen", "helo", "dwell", "belle"},
        "dick": {"dickens", "richard", "dictionary"},
        "cock": {"cockney", "peacock", "cockatoo", "cockerel", "hancock"},
        "prick": {"prickle", "lipstick"},
        "crap": {"crapper", "crappy"},
        "bitch": {"bitchy"},
        "kys": set(),  # no safe variants — always flag
    },
    min_word_length=2,
    version="1.2.0",
    description="English profanity and toxicity word list with stemmer",
    author="LPTE Contributors",
)
