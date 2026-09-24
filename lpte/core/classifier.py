"""
Multi-signal toxicity classifier.

Scoring approach:
1. Exact / stemmed match (merged single loop) → confidence 1.0 / 0.85
2. Phrase match (bigrams/trigrams vs bad_word phrases) → confidence 0.80
3. Concatenated-word match (split bypasses like "f u c k") → confidence 0.70
4. Fuzzy match (edit distance ≤ 1) → confidence 0.65

Context rules suppress false positives: if a bad word has context rules
and the input word is a known clean variant, the match is skipped.
Multi-word clean entries (idioms such as "পাগলের মতো") suppress matches
when the full phrase appears in the raw text; single-word clean variants
only suppress at word level — a benign word elsewhere in the text never
masks real toxicity (e.g. "passed" no longer hides "ass").

min_word_length from LanguageProfile is enforced before any matching.

Matched terms are mapped to content categories (slur / threat / sexual /
profanity) via LanguageProfile.word_categories. Slur and threat matches
escalate severity by one level, reflecting real-world moderation practice
where identity attacks and threats warrant stronger action than plain
profanity at the same confidence.

Performance notes (on-device focus):
- Per-profile lookup structures (multi-word phrase set, vocabulary length
  index, SymSpell-style delete-1 neighborhood for fuzzy matching) are built
  once and cached on the Classifier instance.
- Fuzzy matching is O(word_length) per token instead of O(vocabulary):
  candidate bad words are pulled from a delete-1 index, then verified with
  the exact edit-distance-1 predicate (identical semantics, no
  transposition false positives).
- Concatenation matching checks vocabulary-length slices against the word
  set instead of substring-scanning the whole vocabulary per window.
- Stemming is memoized per classify() call — bigram/trigram words overlap
  heavily with unigrams.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import IntEnum

from lpte.core.profile import LanguageProfile
from lpte.core.tokenizer import TokenizationResult


class Severity(IntEnum):
    """Toxicity severity levels."""

    NONE = 0
    LOW = 1
    MEDIUM = 2
    HIGH = 3
    CRITICAL = 4


# ─── Content Categories ───────────────────────────────────────────────────────

CATEGORY_PROFANITY = "profanity"   # default for unmatched vocabulary entries
CATEGORY_SLUR = "slur"             # identity-based attacks
CATEGORY_THREAT = "threat"         # violence, self-harm incitement
CATEGORY_SEXUAL = "sexual"         # sexually explicit / degrading terms

# Categories that escalate severity by one level when matched.
_ESCALATING_CATEGORIES = frozenset({CATEGORY_SLUR, CATEGORY_THREAT})

# Categories that can never reach CRITICAL on their own. Two insult words
# score the same as two slurs (confidence counts matches, not harm), so
# without this cap "you are so stupid and ugly" would rank alongside a death
# threat. CRITICAL is reserved for identity attacks, threats and sexual harm.
_CAP_AT_HIGH_CATEGORIES = frozenset({CATEGORY_PROFANITY, "insult"})


@dataclass
class ClassificationResult:
    """Full result of a toxicity classification."""

    is_toxic: bool
    severity: Severity
    confidence: float
    matched_terms: list[str]
    signals: dict[str, int] = field(default_factory=dict)
    # Content categories of matched terms (e.g. ["profanity", "slur"]).
    categories: list[str] = field(default_factory=list)
    # Language code of the engine that produced this result (set by
    # MultiLangEngine; empty for single-language engines).
    language: str = ""


# ─── Helpers ──────────────────────────────────────────────────────────────────

def _edit_distance_1(s: str, t: str) -> bool:
    """Check if two strings differ by at most 1 edit (insert, delete, substitute)."""
    if abs(len(s) - len(t)) > 1:
        return False
    if len(s) > len(t):
        s, t = t, s
    i = j = 0
    edits = 0
    while i < len(s) and j < len(t):
        if s[i] == t[j]:
            i += 1
            j += 1
        else:
            edits += 1
            if edits > 1:
                return False
            if len(s) == len(t):
                i += 1
                j += 1
            else:
                j += 1
    return True


def _find_all(haystack: str, needle: str) -> list[int]:
    """Return start offsets of every (possibly overlapping) occurrence."""
    out: list[int] = []
    start = haystack.find(needle)
    while start != -1:
        out.append(start)
        start = haystack.find(needle, start + 1)
    return out


# Articles/determiners skipped when looking for the object that follows a
# matched phrase: "kill the process" and "kill process" mean the same thing.
_DETERMINERS = frozenset(
    {
        "a", "an", "the", "this", "that", "these", "those",
        "my", "your", "his", "her", "its", "our", "their",
        "some", "any", "all", "no",
    }
)

# Coordinators that signal another target is coming after the object.
_COORDINATORS = frozenset({"and", "or", "then", "before", "after", "but"})

# Words that make a coordinated second target a person, not a thing.
# Deliberately excludes "boss" (everyday gaming vocabulary) and first-person
# pronouns, which usually start a new clause rather than name a target
# ("kill the process and I'll restart it").
_PERSON_TARGETS = frozenset(
    {
        "you", "u", "your", "yourself", "yourselves", "him", "her", "them",
        "us", "me", "everyone", "everybody", "someone", "somebody",
        "people", "kids", "children", "family", "wife", "husband",
        "girlfriend", "boyfriend", "mother", "father", "mom", "dad",
        "brother", "sister", "friend", "friends", "neighbours", "neighbors",
        "students", "teacher", "coworkers", "colleagues",
    }
)


def _benign_object_follows(raw_text: str, phrase: str, objects: set[str]) -> bool:
    """
    True when every occurrence of `phrase` is followed by a benign object.

    "I will kill the process" → the object of "will kill" is a process, so
    the phrase is ordinary technical speech, not a threat. "I will kill the
    process and then you" → only one of the two occurrences is benign, so we
    report the match: when in doubt, flag.
    """
    phrase_len = len(phrase)
    for start in _find_all(raw_text, phrase):
        tail = raw_text[start + phrase_len : start + phrase_len + 40]
        # Content words that follow the phrase, determiners removed.
        following: list[str] = []
        for token in tail.split():
            token = token.strip(".,!?;:'\"()[]")
            if not token or token in _DETERMINERS:
                continue
            following.append(token)
            if len(following) >= 4:
                break

        # "kill the process and you" — a benign object must never mask a
        # second, personal target. Checked over the whole window first, so an
        # early benign object cannot hide it.
        for i, token in enumerate(following):
            if (
                token in _COORDINATORS
                and i + 1 < len(following)
                and following[i + 1] in _PERSON_TARGETS
            ):
                return False

        if not any(token in objects for token in following):
            return False
    return True


def _is_context_clean(
    word: str,
    bad_word: str,
    context_rules: dict[str, set[str]],
    raw_text: str = "",
) -> bool:
    """
    Check if a matched bad word is actually a known-benign usage.

    Two mechanisms, both deliberately narrow:

    1. Word-level: the matched token *is* a known clean variant
       (e.g. the word "class" for bad word "ass").
    2. Coverage: every occurrence of the bad word's literal form in the raw
       text lies inside an occurrence of a benign compound/idiom that contains
       it. This is what makes unspaced scripts work — Japanese "豚" (insult)
       is clean inside "豚肉" (pork), Bengali "পাগল" is clean inside the
       idiom "পাগলের মতো".

    Crucially, a benign word appearing *elsewhere* in the text never masks a
    real match: "I passed the exam, you ass" still flags "ass", because the
    second occurrence is not covered by "pass".
    """
    clean_words = context_rules.get(bad_word)
    if not clean_words:
        return False
    if word in clean_words:
        return True
    if not raw_text:
        return False

    # Only compounds/idioms that actually contain the bad word can cover it.
    covering = [c for c in clean_words if bad_word in c]
    if not covering:
        return False

    starts = _find_all(raw_text, bad_word)
    if not starts:
        # Matched via stemming/obfuscation — the literal form is absent, so
        # coverage cannot be established. Do not suppress (favour detection).
        return False

    end = len(raw_text)
    bad_len = len(bad_word)
    covered = [False] * len(starts)
    remaining = len(starts)
    for clean in covering:
        clean_len = len(clean)
        limit = end - clean_len
        for cs in _find_all(raw_text, clean):
            for k, s in enumerate(starts):
                if not covered[k] and cs <= s and s + bad_len <= cs + clean_len:
                    covered[k] = True
                    remaining -= 1
        if remaining == 0:
            return True
    return False


# ─── Precomputed Profile Index ────────────────────────────────────────────────

class _ProfileIndex:
    """
    Lookup structures derived from a profile's vocabulary. Built once per
    profile and cached on the Classifier. Holds a strong reference to the
    bad_words set so its id() can never be recycled while cached.
    """

    __slots__ = (
        "bad_words",
        "multiword",
        "multiword_starts",
        "single_lengths",
        "fuzzy_index",
        "has_multiword",
    )

    # Fuzzy matching only applies to words of at least this length on both
    # sides (guards against false positives from short common words).
    MIN_FUZZY_LEN = 5

    def __init__(self, bad_words: set[str]) -> None:
        self.bad_words = bad_words
        self.multiword = frozenset(w for w in bad_words if " " in w)
        self.has_multiword = bool(self.multiword)
        # First words of every multi-word entry — lets the phrase scan
        # reject an n-gram with one hash lookup instead of building it.
        self.multiword_starts = frozenset(w.split(" ", 1)[0] for w in self.multiword)
        self.single_lengths = sorted({len(w) for w in bad_words if " " not in w})

        # SymSpell-style delete-1 neighborhood: each bad word (len >= 5) is
        # indexed under itself and all single-character deletions. A query
        # word within edit distance 1 shares at least one key.
        fuzzy_index: dict[str, list[str]] = {}
        for w in sorted(bad_words):
            if " " in w or len(w) < self.MIN_FUZZY_LEN:
                continue
            keys = {w}
            for i in range(len(w)):
                keys.add(w[:i] + w[i + 1:])
            for k in keys:
                bucket = fuzzy_index.get(k)
                if bucket is None:
                    fuzzy_index[k] = [w]
                else:
                    bucket.append(w)  # sorted iteration → deterministic order
        self.fuzzy_index = fuzzy_index

    def fuzzy_candidates(self, word: str):
        """Yield vocabulary candidates within edit distance 1 of word (may repeat)."""
        idx = self.fuzzy_index
        cands = idx.get(word)
        if cands:
            yield from cands
        for i in range(len(word)):
            cands = idx.get(word[:i] + word[i + 1:])
            if cands:
                yield from cands


# ─── Classifier ───────────────────────────────────────────────────────────────

class Classifier:
    """Classifies tokenized text against a language profile."""

    # Upper bound for the cross-call stem memo. Chat traffic repeats the same
    # vocabulary heavily, and multi-variant analysis re-stems the same words,
    # so this trades a small fixed memory budget for a large steady-state win.
    STEM_MEMO_MAX = 4096

    def __init__(self) -> None:
        # id(bad_words) → (len(bad_words), index). The length guard makes a
        # stale entry (mutated set) rebuild instead of serving wrong lookups.
        self._indexes: dict[int, tuple[int, _ProfileIndex]] = {}
        # Persistent stem memo, keyed per stemmer instance.
        self._stem_cache: dict[str, str] = {}
        self._stem_cache_stemmer: int | None = None

    def _get_index(self, bad_words: set[str]) -> _ProfileIndex:
        key = id(bad_words)
        entry = self._indexes.get(key)
        if entry is not None and entry[0] == len(bad_words):
            return entry[1]
        index = _ProfileIndex(bad_words)
        self._indexes[key] = (len(bad_words), index)
        return index

    def classify(
        self,
        tokens: TokenizationResult,
        profile: LanguageProfile,
        threshold: float = 0.6,
    ) -> ClassificationResult:
        matched_terms: list[str] = []
        signals: dict[str, int] = {
            "exact_match": 0,
            "stemmed_match": 0,
            "phrase_match": 0,
            "concat_match": 0,
            "fuzzy_match": 0,
        }

        bad_words = profile.bad_words
        min_len = profile.min_word_length
        context_rules = profile.context_rules
        benign_objects = profile.benign_objects
        raw_text = tokens.raw_normalized
        index = self._get_index(bad_words)

        # Stem memoization: bigram/trigram words overlap unigrams, and the
        # same words recur across the normalization variants and across
        # messages. Rebound when the stemmer changes; capped to bound memory.
        stemmer_id = id(profile.stemmer)
        if self._stem_cache_stemmer != stemmer_id:
            self._stem_cache.clear()
            self._stem_cache_stemmer = stemmer_id
        elif len(self._stem_cache) > self.STEM_MEMO_MAX:
            self._stem_cache.clear()
        stem_cache: dict[str, str] = self._stem_cache
        stemmer_stem = profile.stemmer.stem

        def stem(w: str) -> str:
            s = stem_cache.get(w)
            if s is None:
                s = stemmer_stem(w)
                stem_cache[w] = s
            return s

        # Filter words by min_word_length for exact/stemmed matching
        words = [w for w in tokens.words if len(w) >= min_len]
        # Keep ALL words (including single chars) for concat detection
        all_words = tokens.words

        # ── Signal 1: Exact + Stemmed match (single merged loop) ──────────────
        # Stem each word once and check both the stemmed and original forms.
        for word in words:
            if word in bad_words:
                if not _is_context_clean(word, word, context_rules, raw_text):
                    matched_terms.append(word)
                    signals["exact_match"] += 1
                    continue

            stemmed = stem(word)
            if stemmed != word and stemmed in bad_words:
                if not _is_context_clean(word, stemmed, context_rules, raw_text):
                    matched_terms.append(stemmed)
                    signals["stemmed_match"] += 1

        # ── Signal 2: Phrase match — bigrams and trigrams vs bad word set ──────
        # This catches multi-word toxic phrases not caught by single-word matching.
        #
        # This signal is NOT gated on "nothing matched yet", unlike the concat
        # and fuzzy fallbacks below. Multi-word entries are where the highest
        # harm lives — "kill yourself", "gonna kill", "kill you" — and a cheap
        # single-word hit must never hide them: "you are such an idiot, go kill
        # yourself" has to score as a threat, not as an insult with a side of
        # profanity. Gating this signal was a performance shortcut that traded
        # away the detection that matters most.
        #
        # Cost is bounded: one hash lookup per n-gram in the common case, with
        # the join/stem work done only when the profile can actually match it.
        multiword = index.multiword
        has_multiword = index.has_multiword
        lengths = index.single_lengths
        starts = index.multiword_starts
        for ngram in tokens.bigrams + tokens.trigrams:
            # Cheapest possible gate: a multi-word entry can only match if
            # the n-gram starts with a word that starts some entry. Most
            # n-grams die here, which is what keeps this signal affordable
            # now that it runs on every message.
            space = ngram.find(" ")
            head = ngram if space < 0 else ngram[:space]
            can_phrase = head in starts or (has_multiword and stem(head) in starts)

            matched_bad = None
            if can_phrase and ngram in multiword:
                matched_bad = ngram
            else:
                # Space-stripped form: catches a vocabulary word split across
                # two tokens ("fuc king"). Length-filtered first — a joined
                # n-gram can only match a vocabulary word of exactly its
                # length, which rejects nearly all candidates before we pay
                # for the string allocation.
                joined_len = len(ngram) - ngram.count(" ")
                if joined_len in lengths:
                    ngram_joined = ngram.replace(" ", "")
                    if ngram_joined in bad_words:
                        matched_bad = ngram_joined
            if matched_bad is not None:
                if not _is_context_clean(ngram, matched_bad, context_rules, raw_text):
                    benign = benign_objects.get(matched_bad)
                    if benign and _benign_object_follows(raw_text, matched_bad, benign):
                        # Ordinary technical/idiomatic usage — keep scanning,
                        # a later n-gram may still be a real phrase.
                        continue
                    matched_terms.append(ngram)
                    signals["phrase_match"] += 1
                    break
            # A stemmed n-gram still contains a space, so it can only match
            # multi-word vocabulary entries — skip when the profile has none.
            # The join is only worth doing when stemming actually changes a
            # word; otherwise the stemmed form equals what we already tested.
            if can_phrase and has_multiword:
                parts = ngram.split()
                stemmed_parts = [stem(w) for w in parts]
                if stemmed_parts == parts:
                    continue
                stemmed_ngram = " ".join(stemmed_parts)
                if stemmed_ngram in multiword:
                    if not _is_context_clean(ngram, stemmed_ngram, context_rules, raw_text):
                        benign = benign_objects.get(stemmed_ngram)
                        if benign and _benign_object_follows(
                            raw_text, stemmed_ngram, benign
                        ):
                            continue
                        matched_terms.append(stemmed_ngram)
                        signals["phrase_match"] += 1
                        break

        # ── Signal 3: Concatenated-word detection ("f u c k" → "fuck") ─────────
        # Uses all_words (unfiltered) so single-char split words are included.
        if not matched_terms and len(all_words) >= 2:
            lengths = index.single_lengths
            n_words = len(all_words)
            for window_size in range(2, min(n_words + 1, 6)):
                found = False
                for i in range(n_words - window_size + 1):
                    window = all_words[i: i + window_size]
                    # Only try windows of short single-char/double-char words
                    if all(len(w) <= 3 for w in window):
                        concatenated = "".join(window)
                        concat_len = len(concatenated)
                        # Slice-based substring search: a vocabulary word is a
                        # substring iff some length-matched slice equals it.
                        term = None
                        for bl in lengths:
                            if bl > concat_len:
                                break
                            for pos in range(concat_len - bl + 1):
                                cand = concatenated[pos: pos + bl]
                                if cand in bad_words and not _is_context_clean(
                                    concatenated, cand, context_rules, raw_text
                                ):
                                    term = cand
                                    break
                            if term is not None:
                                break
                        if term is not None:
                            matched_terms.append(term)
                            signals["concat_match"] += 1
                            found = True
                            break
                    if found:
                        break
                if found:
                    break

        # ── Signal 4: Fuzzy matching — edit distance ≤ 1 ─────────────────────
        # Require both word and bad_word to be >= 5 chars to avoid false
        # positives from short common words ("today", "you", "are", etc.).
        #
        # The first character must also match. Obfuscation has to stay
        # readable to land, so it preserves the initial letter ("fukc",
        # "ashole", "sh1t"); a first-letter change produces a *different
        # word*, not a disguised one. Without this guard, French "bonne
        # journée" (good day) matches "conne" and German "Penner" matches
        # "Penis" — exactly the false positives that make a filter
        # unusable in a language you don't speak.
        #
        # Candidates come from the delete-1 index, then are verified with the
        # exact edit-distance predicate (no transposition false positives).
        if not matched_terms:
            min_fuzzy = _ProfileIndex.MIN_FUZZY_LEN
            for word in words:
                if len(word) < min_fuzzy:
                    continue
                tried: set[str] = set()
                for cand in index.fuzzy_candidates(word):
                    if cand in tried or cand[0] != word[0]:
                        continue
                    tried.add(cand)
                    if _edit_distance_1(word, cand) and not _is_context_clean(
                        word, cand, context_rules, raw_text
                    ):
                        matched_terms.append(cand)
                        signals["fuzzy_match"] += 1
                        break

        # ── Confidence calculation ─────────────────────────────────────────────
        confidence = 0.0

        if signals["exact_match"] > 0:
            confidence = min(0.6 + signals["exact_match"] * 0.2, 1.0)

        if signals["stemmed_match"] > 0:
            confidence = max(confidence, min(0.5 + signals["stemmed_match"] * 0.2, 0.9))

        if signals["phrase_match"] > 0:
            confidence = max(confidence, min(0.5 + signals["phrase_match"] * 0.2, 0.85))

        if signals["concat_match"] > 0:
            confidence = max(confidence, min(0.5 + signals["concat_match"] * 0.2, 0.85))

        if signals["fuzzy_match"] > 0:
            confidence = max(confidence, min(0.5 + signals["fuzzy_match"] * 0.15, 0.75))

        # ── Severity mapping ──────────────────────────────────────────────────
        if confidence >= 0.9:
            severity = Severity.CRITICAL
        elif confidence >= 0.7:
            severity = Severity.HIGH
        elif confidence >= 0.4:
            severity = Severity.MEDIUM
        elif confidence > 0:
            severity = Severity.LOW
        else:
            severity = Severity.NONE

        # ── Categories & severity escalation ──────────────────────────────────
        # Deterministic dedupe (order-preserving) instead of set() iteration.
        unique_terms = list(dict.fromkeys(matched_terms))
        categories: list[str] = []
        if unique_terms:
            word_categories = profile.word_categories
            cat_set = {word_categories.get(t, CATEGORY_PROFANITY) for t in unique_terms}
            categories = sorted(cat_set)
            # Slurs and threats escalate one severity level (capped): identity
            # attacks warrant stronger action at the same confidence.
            if cat_set & _ESCALATING_CATEGORIES:
                if severity > Severity.NONE:
                    severity = Severity(min(severity + 1, Severity.CRITICAL))
            elif cat_set <= _CAP_AT_HIGH_CATEGORIES:
                # Swearing and insults only — never critical on their own.
                severity = Severity(min(severity, Severity.HIGH))

        return ClassificationResult(
            is_toxic=confidence >= threshold,
            severity=severity,
            confidence=confidence,
            matched_terms=unique_terms,
            signals=signals,
            categories=categories,
        )
