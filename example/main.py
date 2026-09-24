#!/usr/bin/env python3
"""
LPTE Demo — real-world usage of the toxicity engine.

Run: python -m example.main

Shows the four things an integrator actually needs:
1. Detect        — is this message toxic?
2. Categorise    — what KIND of harm is it? (swear vs slur vs threat)
3. Decide        — what should the app DO about it? (allow/flag/mask/block)
4. Sanitize      — what do we show the reader?
"""

from lpte import (
    Action,
    LpteEngine,
    MultiLangEngine,
    get_policy,
)
from lpte.languages import BengaliProfile, EnglishProfile


def divider(title: str) -> None:
    print(f"\n{'=' * 66}\n{title}\n{'=' * 66}")


def demo_detection() -> None:
    divider("1. DETECTION — plain toxicity analysis")
    engine = LpteEngine(EnglishProfile)

    for text in [
        "Hello, how are you today?",
        "The weather is beautiful",
        "you are a fucking idiot",
        "f4ck this bullsh1t",
        "class assessment was great",
    ]:
        result = engine.analyze(text)
        status = "TOXIC" if result.is_toxic else "CLEAN"
        print(f"  [{status}] {text!r}")
        if result.is_toxic:
            print(f"          severity={result.severity.name} "
                  f"confidence={result.confidence:.2f} "
                  f"terms={result.matched_terms}")


def demo_categories() -> None:
    divider("2. CATEGORIES — not all toxicity is equal")
    engine = LpteEngine(EnglishProfile)

    for text in [
        "this is bullshit",
        "you are so stupid and ugly",
        "you nigger",
        "I will kill you",
    ]:
        result = engine.analyze(text)
        print(f"  {text!r:32} → {str(result.categories):26} "
              f"severity={result.severity.name}")


def demo_policy() -> None:
    divider("3. POLICY — what should the app actually DO?")
    engine = LpteEngine(EnglishProfile)

    messages = [
        "hello everyone",
        "damn this is good",
        "you are so stupid",
        "you nigger",
        "I will kill you",
        "please kill the background process",
    ]

    policies = {name: get_policy(name) for name in ("strict", "balanced", "lenient")}
    print(f"  {'message':38} {'strict':8} {'balanced':9} lenient")
    print("  " + "-" * 62)
    for text in messages:
        result = engine.analyze(text)
        actions = [policies[n].decide(result).action.name for n in
                   ("strict", "balanced", "lenient")]
        print(f"  {text[:37]:38} {actions[0]:8} {actions[1]:9} {actions[2]}")

    print("\n  Legend: ALLOW=publish  FLAG=publish+review  "
          "MASK=publish censored  BLOCK=reject")


def demo_sanitize() -> None:
    divider("4. SANITIZE — masking obfuscated abuse")
    engine = LpteEngine(EnglishProfile)

    for text in [
        "you are a bastard",
        "f4ck this bullsh1t",
        "f.u.c.k you",
        "shiiit happens",
        "f u c k off",
        "you @sshole",
    ]:
        print(f"  {text!r:24} → {engine.sanitize(text)!r}")


def demo_code_switching() -> None:
    divider("5. CODE-SWITCHING — mixed Bengali/English chat (Banglish)")
    engine = MultiLangEngine([BengaliProfile, EnglishProfile])

    for text in [
        "আমি বাংলায় কথা বলি",
        "তুই একদম idiot",
        "কুত্তা",
        "hello how are you",
        "you fucking idiot",
    ]:
        result = engine.analyze(text)
        status = "TOXIC" if result.is_toxic else "CLEAN"
        lang = result.language or "-"
        print(f"  [{status}] ({lang:5}) {text}")
        if result.is_toxic:
            print(f"          terms={result.matched_terms} "
                  f"sanitized={engine.sanitize(text)!r}")


def demo_bengali_false_positives() -> None:
    divider("6. BENGALI FALSE-POSITIVE FIXES")
    engine = LpteEngine(BengaliProfile)

    print("  These ordinary sentences must NOT be flagged:")
    for text in [
        "আমার মায়ের হাতের রান্না খুব ভালো",
        "আমি আমার বোনের সাথে বাজারে গিয়েছিলাম",
        "গরুর দুধ খুব পুষ্টিকর",
        "ফোনটা নষ্ট হয়ে গেছে",
        "আমি মুসলিম",
    ]:
        result = engine.analyze(text)
        flag = "OK  " if not result.is_toxic else "FAIL"
        print(f"  [{flag}] {text}")

    print("\n  Genuine Bengali abuse must still be caught:")
    for text in ["কুত্তা", "হারামজাদা", "মাদারচোদ", "তুই একটা গাধা"]:
        result = engine.analyze(text)
        flag = "OK  " if result.is_toxic else "FAIL"
        print(f"  [{flag}] {text}  → {result.matched_terms}")


def demo_performance() -> None:
    divider("7. PERFORMANCE")
    import time

    engine = LpteEngine(EnglishProfile, cache_size=0)
    texts = [
        "hello how are you today",
        "the deployment finished and all tests are green, great work team",
        " ".join("word%d" % i for i in range(120)),
        "you are a fucking idiot",
    ]
    for _ in texts:
        engine.analyze(_)

    total = 0.0
    n = 0
    t0 = time.perf_counter()
    for _ in range(200):
        for t in texts:
            engine.analyze(t)
            n += 1
    total = (time.perf_counter() - t0) * 1000
    print(f"  {n} analyses in {total:.0f} ms")
    print(f"  average: {total / n:.3f} ms per message")
    print(f"  throughput: {n / (total / 1000):.0f} messages/sec")


def main() -> None:
    print("\n  LPTE — Local Profanity & Toxicity Engine")
    print("  100% offline · zero dependencies · runs on-device\n")
    demo_detection()
    demo_categories()
    demo_policy()
    demo_sanitize()
    demo_code_switching()
    demo_bengali_false_positives()
    demo_performance()
    print("\n" + "=" * 66)
    print("  Done. No network calls were made — everything ran locally.\n")


if __name__ == "__main__":
    main()
