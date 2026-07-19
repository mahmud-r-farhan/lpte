"""
LpteEngine — high-level API for toxicity analysis.

This is the primary entry point for consuming the library.

Usage:
    from lpte import LpteEngine
    from lpte.languages import EnglishProfile

    engine = LpteEngine(EnglishProfile)
    result = engine.analyze("some text")
    if result.is_toxic:
        print(f"Toxic: {result.severity} ({result.confidence})")
"""

from __future__ import annotations

import re

from lpte.core.classifier import ClassificationResult, Classifier, Severity
from lpte.core.normalizer import TextNormalizer
from lpte.core.profile import LanguageProfile
from lpte.core.tokenizer import Tokenizer


class LpteEngine:
    """High-level toxicity analysis engine."""

    def __init__(self, profile: LanguageProfile):
        self.profile = profile
        self.normalizer = TextNormalizer()
        self.tokenizer = Tokenizer()
        self.classifier = Classifier()

    def analyze(self, text: str, threshold: float = 0.6) -> ClassificationResult:
        """
        Analyze text for toxic content.
        Tries multiple normalization variants to catch obfuscation.
        """
        # Try primary normalization first
        normalized = self.normalizer.normalize(text)
        tokens = self.tokenizer.tokenize(normalized)
        result = self.classifier.classify(tokens, self.profile, threshold)
        if result.is_toxic:
            return result

        # Try alternative normalizations (leet alternatives, aggressive collapse)
        variants = self.normalizer.normalize_with_alternatives(text)
        for variant in variants[1:]:  # skip primary (already tried)
            tokens = self.tokenizer.tokenize(variant)
            variant_result = self.classifier.classify(tokens, self.profile, threshold)
            if variant_result.is_toxic:
                return variant_result
            # Keep the best result if nothing is toxic
            if variant_result.confidence > result.confidence:
                result = variant_result

        return result

    def is_toxic(self, text: str, threshold: float = 0.6) -> bool:
        """Quick check: is the text toxic?"""
        return self.analyze(text, threshold).is_toxic

    def sanitize(self, text: str, mask: str = "*") -> str:
        """
        Sanitize text by replacing toxic segments with a mask.
        """
        result = self.analyze(text)
        if not result.is_toxic:
            return text

        sanitized = text
        for term in result.matched_terms:
            pattern = re.compile(r"\b" + re.escape(term) + r"\b", re.IGNORECASE)
            sanitized = pattern.sub(lambda m: mask * len(m.group()), sanitized)

        return sanitized
