"""
LPTE — Local Profanity & Toxicity Engine

Zero-cost, high-performance, on-device text toxicity analysis.
"""

from lpte.core.engine import (
    THRESHOLD_BALANCED,
    THRESHOLD_LENIENT,
    THRESHOLD_STRICT,
    LpteEngine,
)
from lpte.core.classifier import ClassificationResult, Severity
from lpte.core.normalizer import TextNormalizer
from lpte.core.tokenizer import Tokenizer, TokenizationResult
from lpte.core.profile import LanguageProfile
from lpte.core.loader import LanguagePackLoader
from lpte.core.cache import LRUCache
from lpte.core.multilang import MultiLangEngine, detect_scripts
from lpte.core.policy import (
    POLICY_PRESETS,
    Action,
    ModerationPolicy,
    PolicyDecision,
    get_policy,
    policy_balanced,
    policy_lenient,
    policy_strict,
)

__version__ = "1.2.0"
__all__ = [
    # Core
    "LpteEngine",
    "MultiLangEngine",
    "detect_scripts",
    "ClassificationResult",
    "Severity",
    "TextNormalizer",
    "Tokenizer",
    "TokenizationResult",
    "LanguageProfile",
    "LanguagePackLoader",
    "LRUCache",
    # Moderation policy
    "ModerationPolicy",
    "PolicyDecision",
    "Action",
    "POLICY_PRESETS",
    "get_policy",
    "policy_strict",
    "policy_balanced",
    "policy_lenient",
    # Threshold presets
    "THRESHOLD_STRICT",
    "THRESHOLD_BALANCED",
    "THRESHOLD_LENIENT",
]
