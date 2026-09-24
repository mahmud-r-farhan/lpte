"""Moderation decisions on top of language-agnostic detection results.

Presets are examples, not universal cultural rules. Threats/slurs only receive
an automatic BLOCK when an explicit rule matched above the category threshold.
Allowlist and denylist are policy-level: they never mutate the engine's data.
"""

from __future__ import annotations

import re
from collections import Counter
from dataclasses import dataclass, field
from enum import Enum

from lpte.core.classifier import ClassificationResult, confidence_from_signals, validate_threshold
from lpte.core.normalizer import TextNormalizer
from lpte.core.profile import CATEGORIES


class Action(str, Enum):
    ALLOW = "ALLOW"
    FLAG = "FLAG"
    MASK = "MASK"
    BLOCK = "BLOCK"


@dataclass(frozen=True)
class ModerationDecision:
    action: Action
    reason: str
    categories: tuple[str, ...]
    matched_terms: tuple[str, ...]
    confidence: float

    def as_dict(self) -> dict[str, object]:
        return {
            "action": self.action.value,
            "reason": self.reason,
            "categories": list(self.categories),
            "matched_terms": list(self.matched_terms),
            "confidence": round(self.confidence, 4),
        }


def _contains(text: str, term: str) -> bool:
    """Whole Latin words/phrases, or subwords in unspaced CJK text."""
    if any(0x3400 <= ord(c) <= 0x9FFF for c in term):
        return term in text
    return re.search(r"(?<!\w)" + re.escape(term) + r"(?!\w)", text) is not None


@dataclass
class ModerationPolicy:
    category_thresholds: dict[str, float] = field(default_factory=dict)
    mask_above: float | None = 0.6
    block_above: float | None = 0.9
    allowlist: set[str] = field(default_factory=set)
    denylist: set[str] = field(default_factory=set)

    def __post_init__(self) -> None:
        if set(self.category_thresholds) - CATEGORIES:
            raise ValueError("unknown moderation category")
        for v in self.category_thresholds.values():
            validate_threshold(v)
        for v in (self.mask_above, self.block_above):
            if v is not None:
                validate_threshold(v)
        if (
            self.mask_above is not None
            and self.block_above is not None
            and self.mask_above > self.block_above
        ):
            raise ValueError("mask_above must not exceed block_above")
        if any(not isinstance(v, str) or not v.strip() for v in self.allowlist | self.denylist):
            raise ValueError("allowlist/denylist terms must be non-empty strings")

    def decide(self, result: ClassificationResult, text: str | None = None) -> ModerationDecision:
        """Decide independently of ``result.is_toxic``'s global threshold.

        Pass ``text`` if denylist terms may not appear in the engine vocabulary;
        this also lets a custom denylist block an otherwise CLEAN message.
        """
        norm = TextNormalizer()
        denied = {norm.normalize(term) for term in self.denylist}
        original = norm.normalize(text) if text is not None and denied else ""
        for term in sorted(denied):
            if (text is not None and _contains(original, term)) or term in result.matched_terms:
                return ModerationDecision(
                    Action.BLOCK,
                    f"denylist term: {term}",
                    tuple(result.categories),
                    (term,),
                    result.confidence,
                )

        allowed = {norm.normalize(term) for term in self.allowlist}
        matches = [m for m in result.matches if m.term not in allowed]
        if result.matches:
            # Alternative normalizations of one surface must not double count.
            counts: dict[str, int] = {}
            for source in {(m.language, m.variant) for m in matches}:
                for name, count in Counter(
                    m.signal for m in matches if (m.language, m.variant) == source
                ).items():
                    counts[name] = max(counts.get(name, 0), count)
            confidence = confidence_from_signals(counts)
            categories = tuple(dict.fromkeys(m.category for m in matches))
            terms = tuple(dict.fromkeys(m.term for m in matches))
        else:
            terms = tuple(t for t in result.matched_terms if t not in allowed)
            confidence = result.confidence if terms else 0.0
            categories = tuple(result.categories) if terms else ()

        if not terms:
            return ModerationDecision(Action.ALLOW, "no unallowlisted terms", (), (), 0.0)
        active = {c for c in categories if confidence >= self.category_thresholds.get(c, 0.6)}
        if not active:
            return ModerationDecision(
                Action.ALLOW, "below category threshold", categories, terms, confidence
            )
        if active & {"slur", "threat"}:
            return ModerationDecision(
                Action.BLOCK, "high-harm category", categories, terms, confidence
            )
        if self.block_above is not None and confidence >= self.block_above:
            action, reason = Action.BLOCK, "above block threshold"
        elif self.mask_above is not None and confidence >= self.mask_above:
            action, reason = Action.MASK, "above mask threshold"
        else:
            action, reason = Action.FLAG, "review recommended"
        return ModerationDecision(action, reason, categories, terms, confidence)


def policy_strict() -> ModerationPolicy:
    return ModerationPolicy(
        category_thresholds={
            "profanity": 0.6,
            "insult": 0.6,
            "sexual": 0.6,
            "slur": 0.6,
            "threat": 0.6,
        },
        mask_above=0.7,
        block_above=0.95,
    )


def policy_balanced() -> ModerationPolicy:
    return ModerationPolicy(
        category_thresholds={
            "profanity": 0.6,
            "insult": 0.6,
            "sexual": 0.6,
            "slur": 0.6,
            "threat": 0.6,
        },
        mask_above=0.7,
        block_above=None,
    )


def policy_lenient() -> ModerationPolicy:
    return ModerationPolicy(
        category_thresholds={
            "profanity": 1.0,
            "insult": 0.6,
            "sexual": 1.0,
            "slur": 0.6,
            "threat": 0.6,
        },
        mask_above=None,
        block_above=None,
    )


POLICY_PRESETS = {
    "strict": policy_strict,
    "balanced": policy_balanced,
    "lenient": policy_lenient,
}


def get_policy(name: str) -> ModerationPolicy:
    try:
        return POLICY_PRESETS[name.lower()]()
    except KeyError as exc:
        raise ValueError(
            f"unknown policy '{name}'; choose {', '.join(sorted(POLICY_PRESETS))}"
        ) from exc
