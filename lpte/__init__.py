"""
LPTE — Local Profanity & Toxicity Engine

Zero-cost, high-performance, on-device text toxicity analysis.
"""

from lpte.core.engine import LpteEngine
from lpte.core.classifier import ClassificationResult, Severity
from lpte.core.normalizer import TextNormalizer
from lpte.core.tokenizer import Tokenizer, TokenizationResult
from lpte.core.profile import LanguageProfile
from lpte.core.loader import LanguagePackLoader

__version__ = "1.0.0"
__all__ = [
    "LpteEngine",
    "ClassificationResult",
    "Severity",
    "TextNormalizer",
    "Tokenizer",
    "TokenizationResult",
    "LanguageProfile",
    "LanguagePackLoader",
]
