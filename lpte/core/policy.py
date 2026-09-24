"""
Moderation policy layer — turns a raw toxicity score into a business action.

Detection alone is not a product. A chat app, a classroom forum and a gaming
lobby all need different responses to the same confidence score. This module
encodes that mapping so integrators configure intent (what to do about each
harm type) instead of hand-tuning thresholds per call site.

Actions (least to most restrictive):
    ALLOW — publish as-is
    FLAG  — publish, but queue for human review / shadow-log
    MASK  — publish with toxic spans replaced (e.g. "f***")
    BLOCK — reject the content, show the user an error

Design notes:
- Thresholds are per content category, because harm is not uniform: a racial
  slur should be blocked at a far lower confidence than a mild swear.
- Denylist entries always BLOCK regardless of score; allowlist entries are
  never blocked on their own (they still surface as FLAG so reviewers keep
  visibility).
- The strictest matching rule wins, so adding a second violation can never
  weaken the response to the first.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import IntEnum

from lpte.core.classifier import (
    CATEGORY_PROFANITY,
    CATEGORY_SEXUAL,
    CATEGORY_SLUR,
    CATEGORY_THREAT,
    ClassificationResult,
    Severity,
)


class Action(IntEnum):
    """What the application should do with the content."""

    ALLOW = 0
    FLAG = 1
    MASK = 2
    BLOCK = 3


# ─── Harm Weights ─────────────────────────────────────────────────────────────
# A raw confidence score says how *certain* the match is, not how *harmful* it
# is — "damn" and a racial slur can both score 0.80. Scaling each category by
# its gravity is what lets one threshold pair separate "mask the swearing"
# from "block the slur", which is how real moderation queues actually behave.
CATEGORY_WEIGHTS: dict[str, float] = {
    CATEGORY_SLUR: 1.30,       # identity attacks — most harm, least context-dependence
    CATEGORY_THREAT: 1.30,     # violence / self-harm incitement
    CATEGORY_SEXUAL: 1.10,
    CATEGORY_PROFANITY: 0.85,  # swearing — often cultural, rarely actionable alone
    "insult": 0.80,            # bullying / personal attacks
}
_DEFAULT_WEIGHT = 0.85


# ─── Preset Policies ──────────────────────────────────────────────────────────

def _preset(
    profanity: float,
    sexual: float,
    slur: float,
    threat: float,
    mask_above: float,
    block_above: float,
) -> "ModerationPolicy":
    return ModerationPolicy(
        category_thresholds={
            CATEGORY_PROFANITY: profanity,
            CATEGORY_SEXUAL: sexual,
            CATEGORY_SLUR: slur,
            CATEGORY_THREAT: threat,
        },
        mask_above=mask_above,
        block_above=block_above,
    )


def policy_strict() -> "ModerationPolicy":
    """
    Kids' apps, classrooms, brand-safe comment sections.

    Tolerates false positives — a wrongly masked word is cheaper than one
    slur reaching a child.
    """
    return _preset(profanity=0.45, sexual=0.40, slur=0.30, threat=0.30,
                   mask_above=0.30, block_above=0.60)


def policy_balanced() -> "ModerationPolicy":
    """
    Default for general communities.

    Swearing is masked; slurs, threats and repeated abuse are blocked.
    """
    return _preset(profanity=0.60, sexual=0.55, slur=0.40, threat=0.40,
                   mask_above=0.55, block_above=0.90)


def policy_lenient() -> "ModerationPolicy":
    """
    Adult forums, gaming voice/text chat.

    Swearing is part of the culture; identity attacks and threats are not.
    """
    return _preset(profanity=0.85, sexual=0.75, slur=0.45, threat=0.35,
                   mask_above=0.75, block_above=0.95)


@dataclass
class PolicyDecision:
    """The outcome of applying a ModerationPolicy to a ClassificationResult."""

    action: Action
    reason: str
    severity: Severity
    confidence: float
    categories: list[str] = field(default_factory=list)
    matched_terms: list[str] = field(default_factory=list)
    # Categories whose score met their own (stricter) threshold.
    triggered_categories: list[str] = field(default_factory=list)
    language: str = ""

    @property
    def should_publish(self) -> bool:
        """True when the content may be shown to its audience as-is."""
        return self.action in (Action.ALLOW, Action.FLAG)

    @property
    def needs_review(self) -> bool:
        return self.action in (Action.FLAG, Action.MASK, Action.BLOCK)

    def as_dict(self) -> dict[str, object]:
        return {
            "action": self.action.name,
            "reason": self.reason,
            "severity": self.severity.name,
            "confidence": round(self.confidence, 4),
            "categories": list(self.categories),
            "triggered_categories": list(self.triggered_categories),
            "matched_terms": list(self.matched_terms),
            "language": self.language,
            "should_publish": self.should_publish,
            "needs_review": self.needs_review,
        }


@dataclass
class ModerationPolicy:
    """
    Maps toxicity signals to a moderation action.

    Args:
        category_thresholds: Minimum confidence at which each content category
            counts as a violation. Categories default to ``default_threshold``.
        default_threshold: Fallback for categories not in the mapping above.
        mask_above: Confidence at or above which the content is masked.
        block_above: Confidence at or above which the content is blocked.
        denylist: Terms that always BLOCK, whatever the score.
        allowlist: Terms that are allowed on their own (downgraded to FLAG).
        always_block_categories: Categories that BLOCK on any violation,
            regardless of confidence (e.g. credible threats).
        preserve_case: Unused placeholder kept for forward compatibility.
    """

    category_thresholds: dict[str, float] = field(default_factory=dict)
    default_threshold: float = 0.6
    mask_above: float = 0.6
    block_above: float = 0.8
    denylist: set[str] = field(default_factory=set)
    allowlist: set[str] = field(default_factory=set)
    always_block_categories: set[str] = field(
        default_factory=lambda: {CATEGORY_THREAT}
    )

    # ─── Decision ─────────────────────────────────────────────────────────────

    def decide(self, result: ClassificationResult) -> PolicyDecision:
        """
        Apply the policy to a classification result.

        Rules, in order of strictness (the strictest match wins):
        1. No violation at all            → ALLOW
        2. A denylisted term is present   → BLOCK
        3. A category in always_block_categories is violated → BLOCK
        4. Any category threshold met     → BLOCK / MASK / FLAG by confidence
        5. Only allowlisted terms matched  → FLAG (visible, but not blocked)
        """
        terms = list(result.matched_terms)
        categories = list(result.categories)
        language = getattr(result, "language", "") or ""

        if not terms or result.confidence <= 0.0:
            return PolicyDecision(
                action=Action.ALLOW,
                reason="no_violation",
                severity=Severity.NONE,
                confidence=result.confidence,
                categories=categories,
                matched_terms=terms,
                language=language,
            )

        # 2. Denylist — overrides everything.
        denied = [t for t in terms if t in self.denylist]
        if denied:
            return self._decision(
                Action.BLOCK, "denylisted_term", result, categories, terms,
                language, denied,
            )

        # Which categories actually meet their own threshold?
        triggered = [
            c for c in categories
            if result.confidence >= self.category_thresholds.get(c, self.default_threshold)
        ]

        # Harm-weighted score: same certainty, different consequences.
        gravity = self.weighted_score(result.confidence, categories)

        # 3. Zero-tolerance categories.
        hard_block = sorted(set(triggered) & set(self.always_block_categories))
        if hard_block:
            return self._decision(
                Action.BLOCK, "zero_tolerance_category", result, categories,
                terms, language, hard_block,
            )

        # 5. Everything matched is explicitly allowlisted → flag only.
        if triggered and all(t in self.allowlist for t in terms):
            return self._decision(
                Action.FLAG, "allowlisted_term", result, categories, terms,
                language, triggered,
            )

        # 4. Harm-graded response.
        if triggered:
            if gravity >= self.block_above:
                action, reason = Action.BLOCK, "high_severity"
            elif gravity >= self.mask_above:
                action, reason = Action.MASK, "medium_severity"
            else:
                action, reason = Action.FLAG, "low_severity"
            return self._decision(
                action, reason, result, categories, terms, language, triggered,
            )

        # Below every category threshold — nothing actionable.
        return PolicyDecision(
            action=Action.ALLOW,
            reason="below_category_threshold",
            severity=result.severity,
            confidence=result.confidence,
            categories=categories,
            matched_terms=terms,
            language=language,
        )

    # ─── Helpers ──────────────────────────────────────────────────────────────

    @staticmethod
    def _decision(
        action: Action,
        reason: str,
        result: ClassificationResult,
        categories: list[str],
        terms: list[str],
        language: str,
        triggered: list[str],
    ) -> PolicyDecision:
        return PolicyDecision(
            action=action,
            reason=reason,
            severity=result.severity,
            confidence=result.confidence,
            categories=categories,
            matched_terms=terms,
            triggered_categories=sorted(set(triggered)),
            language=language,
        )

    def threshold_for(self, category: str) -> float:
        """Effective threshold for a content category."""
        return self.category_thresholds.get(category, self.default_threshold)

    @staticmethod
    def weighted_score(confidence: float, categories: list[str]) -> float:
        """
        Scale a confidence score by the gravity of the categories involved.

        The most severe matching category drives the weight, so a message that
        contains both a swear and a slur is judged by the slur.
        """
        if not categories:
            return min(confidence * _DEFAULT_WEIGHT, 1.0)
        weight = max(CATEGORY_WEIGHTS.get(c, _DEFAULT_WEIGHT) for c in categories)
        return min(confidence * weight, 1.0)


# Convenience mapping so integrators can pick a preset by name.
POLICY_PRESETS: dict[str, callable] = {
    "strict": policy_strict,
    "balanced": policy_balanced,
    "lenient": policy_lenient,
}


def get_policy(name: str) -> ModerationPolicy:
    """Return a built-in policy preset by name (strict/balanced/lenient)."""
    try:
        factory = POLICY_PRESETS[name.lower()]
    except KeyError:
        raise ValueError(
            f"Unknown policy preset '{name}'. "
            f"Available: {sorted(POLICY_PRESETS)}"
        ) from None
    return factory()
