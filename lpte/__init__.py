"""LPTE — offline, rule-based profanity and toxicity detection."""

from lpte.core.cache import LRUCache
from lpte.core.classifier import ClassificationResult, Severity
from lpte.core.engine import LpteEngine
from lpte.core.loader import LanguagePackLoader
from lpte.core.multilang import MultiLangEngine
from lpte.core.normalizer import TextNormalizer
from lpte.core.policy import (
    Action,
    ModerationDecision,
    ModerationPolicy,
    get_policy,
    policy_balanced,
    policy_lenient,
    policy_strict,
)
from lpte.core.profile import LanguageProfile
from lpte.core.tokenizer import TokenizationResult, Tokenizer

__version__ = "1.2.0"
__all__ = [
    "LpteEngine",
    "MultiLangEngine",
    "ClassificationResult",
    "Severity",
    "ModerationPolicy",
    "ModerationDecision",
    "Action",
    "get_policy",
    "policy_strict",
    "policy_balanced",
    "policy_lenient",
    "TextNormalizer",
    "Tokenizer",
    "TokenizationResult",
    "LanguageProfile",
    "LanguagePackLoader",
    "LRUCache",
]
