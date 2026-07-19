#!/usr/bin/env python3
"""
LPTE Demo — example usage of the toxicity engine.

Run: python -m example.main
"""

from lpte import LpteEngine
from lpte.languages import EnglishProfile, BengaliProfile


def main():
    print("=== LPTE Demo ===\n")

    # --- English Analysis ---
    english = LpteEngine(EnglishProfile)

    english_texts = [
        "Hello, how are you today?",
        "The weather is beautiful",
        "f4ck this bullsh1t",
        "you are a bastard",
        "class assessment was great",
    ]

    print("--- English Analysis ---")
    for text in english_texts:
        result = english.analyze(text)
        status = "TOXIC" if result.is_toxic else "CLEAN"
        print(f"[{status}] \"{text}\"")
        if result.is_toxic:
            print(f"  Severity: {result.severity.name}, Confidence: {result.confidence:.2f}")
            print(f"  Matched: {result.matched_terms}")
            print(f"  Signals: {result.signals}")

    # --- Bengali Analysis ---
    bengali = LpteEngine(BengaliProfile)

    bengali_texts = [
        "আমি বাংলায় কথা বলি",
        "কুত্তা",
        "কুত্তারা",
        "আজ আবহাওয়া ভালো",
    ]

    print("\n--- Bengali Analysis ---")
    for text in bengali_texts:
        result = bengali.analyze(text)
        status = "TOXIC" if result.is_toxic else "CLEAN"
        print(f"[{status}] \"{text}\"")
        if result.is_toxic:
            print(f"  Severity: {result.severity.name}, Confidence: {result.confidence:.2f}")
            print(f"  Matched: {result.matched_terms}")

    # --- Sanitization Demo ---
    print("\n--- Sanitization Demo ---")
    dirty = "you are a bastard and a motherfucker"
    clean = english.sanitize(dirty)
    print(f"Original:  {dirty}")
    print(f"Sanitized: {clean}")

    # --- Bypass Detection Demo ---
    print("\n--- Bypass Detection ---")
    bypasses = [
        "f4ck",       # leetspeak
        "f.u.c.k",    # dot separators
        "f u c k",    # word splitting
        "FuCk",       # mixed case
        "shiiit",     # repeated chars
    ]
    for text in bypasses:
        result = english.analyze(text)
        print(f"[{text}] → toxic={result.is_toxic}, signals={result.signals}")


if __name__ == "__main__":
    main()
