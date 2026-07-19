"""
Stemmer interface for language-specific suffix stripping.

Implementations must be deterministic and pure.
"""

from __future__ import annotations

from abc import ABC, abstractmethod


class Stemmer(ABC):
    """Base interface for language-specific stemmers."""

    @abstractmethod
    def stem(self, word: str) -> str:
        """
        Strip inflectional suffixes and return the root form.

        Args:
            word: Input word.

        Returns:
            Root/stemmed form of the word.
        """
        ...
