"""
LPTE command-line interface.

Zero third-party dependencies — usable on any machine with Python 3.9+.

Examples:
    lpte analyze "you are a fucking idiot"
    lpte analyze "তুই একদম idiot" --lang bn+en --policy balanced
    lpte analyze "damn this is good" --json
    lpte sanitize "f4ck this bullsh1t" --mask '#'
    lpte batch messages.txt --lang en --json
    lpte validate languages/bn_profile.json
    lpte languages
    lpte bench
    lpte eval --lang en --verbose
"""

from __future__ import annotations

import argparse
import json
import sys
import time
from pathlib import Path
from typing import Iterable

from lpte.core.engine import LpteEngine
from lpte.core.loader import LanguagePackLoader
from lpte.core.multilang import MultiLangEngine
from lpte.core.policy import Action, ModerationPolicy, POLICY_PRESETS, get_policy
from lpte.eval import evaluate, evaluate_all, overall

# ─── Registry ─────────────────────────────────────────────────────────────────

def _builtin_profiles() -> dict[str, object]:
    """Lazily import built-in profiles (keeps startup fast)."""
    from lpte.languages import (
        ArabicProfile, BengaliProfile, ChineseProfile, EnglishProfile,
        FrenchProfile, GermanProfile, HindiProfile, JapaneseProfile,
        KoreanProfile, RussianProfile, SpanishProfile,
    )
    return {
        "en": EnglishProfile, "bn": BengaliProfile, "zh": ChineseProfile,
        "ja": JapaneseProfile, "ko": KoreanProfile, "ru": RussianProfile,
        "es": SpanishProfile, "hi": HindiProfile, "fr": FrenchProfile,
        "de": GermanProfile, "ar": ArabicProfile,
    }


def available_languages() -> dict[str, object]:
    """Built-in profiles, overlaid with any JSON packs in ./languages."""
    profiles = _builtin_profiles()
    langs_dir = Path.cwd() / "languages"
    if langs_dir.is_dir():
        try:
            for code, profile in LanguagePackLoader.load_directory(langs_dir).items():
                profiles.setdefault(code, profile)
        except Exception:
            pass
    return profiles


def build_engine(lang_spec: str, threshold: float, cache_size: int = 512):
    """
    Build an engine from a language spec.

    ``en``      → single-language engine
    ``bn+en``   → MultiLangEngine over both (for code-switched / romanized chat)
    ``auto``    → MultiLangEngine over every available language
    """
    profiles = available_languages()
    spec = lang_spec.strip().lower()

    if spec in ("auto", "all", "*"):
        codes = list(profiles)
    else:
        codes = [c.strip() for c in spec.replace(",", "+").split("+") if c.strip()]
        unknown = [c for c in codes if c not in profiles]
        if unknown:
            raise SystemExit(
                f"error: unknown language code(s): {unknown}. "
                f"Run 'lpte languages' to list available packs."
            )

    if not codes:
        raise SystemExit("error: no language selected")

    if len(codes) == 1:
        return LpteEngine(profiles[codes[0]], default_threshold=threshold,
                          cache_size=cache_size)
    return MultiLangEngine(
        [profiles[c] for c in codes],
        default_threshold=threshold,
        cache_size=cache_size,
    )


# ─── Output ───────────────────────────────────────────────────────────────────

def _result_payload(result, text: str, policy: ModerationPolicy | None,
                    sanitized: str | None, latency_ms: float | None) -> dict:
    payload = {
        "text": text,
        "is_toxic": result.is_toxic,
        "severity": result.severity.name,
        "confidence": round(result.confidence, 4),
        "categories": list(result.categories),
        "matched_terms": list(result.matched_terms),
        "signals": dict(result.signals),
    }
    if getattr(result, "language", ""):
        payload["language"] = result.language
    if sanitized is not None:
        payload["sanitized"] = sanitized
    if policy is not None:
        decision = policy.decide(result)
        payload["decision"] = decision.as_dict()
    if latency_ms is not None:
        payload["latency_ms"] = round(latency_ms, 3)
    return payload


def _print_human(payload: dict, use_policy: bool) -> None:
    verdict = "TOXIC" if payload["is_toxic"] else "CLEAN"
    print(f"[{verdict}] {payload['text']}")
    print(f"  severity   : {payload['severity']}")
    print(f"  confidence : {payload['confidence']:.2f}")
    if payload["categories"]:
        print(f"  categories : {', '.join(payload['categories'])}")
    if payload["matched_terms"]:
        print(f"  matched    : {', '.join(payload['matched_terms'])}")
    if "sanitized" in payload and payload["sanitized"] != payload["text"]:
        print(f"  sanitized  : {payload['sanitized']}")
    if use_policy and "decision" in payload:
        d = payload["decision"]
        print(f"  action     : {d['action']}  ({d['reason']})")
    if "latency_ms" in payload:
        print(f"  latency    : {payload['latency_ms']:.2f} ms")


# ─── Commands ─────────────────────────────────────────────────────────────────

def cmd_analyze(args) -> int:
    engine = build_engine(args.lang, args.threshold)
    policy = get_policy(args.policy) if args.policy else None
    payloads = []
    t0 = time.perf_counter()
    result = engine.analyze(args.text, args.threshold)
    latency = (time.perf_counter() - t0) * 1000
    sanitized = None
    if args.sanitize and result.is_toxic:
        sanitized = engine.sanitize(args.text, mask=args.mask, threshold=args.threshold)
    payload = _result_payload(result, args.text, policy, sanitized, latency)
    payloads.append(payload)

    if args.json:
        print(json.dumps(payloads[0] if len(payloads) == 1 else payloads,
                         ensure_ascii=False, indent=2))
    else:
        _print_human(payload, policy is not None)
    return 0


def cmd_sanitize(args) -> int:
    engine = build_engine(args.lang, args.threshold)
    out = engine.sanitize(args.text, mask=args.mask, threshold=args.threshold)
    if args.json:
        print(json.dumps({"original": args.text, "sanitized": out},
                         ensure_ascii=False, indent=2))
    else:
        print(out)
    return 0


def cmd_batch(args) -> int:
    path = Path(args.file)
    if not path.exists():
        raise SystemExit(f"error: file not found: {path}")
    lines = [ln.rstrip("\n") for ln in path.read_text(encoding="utf-8").splitlines()]
    texts = [ln for ln in lines if ln.strip()]
    if not texts:
        raise SystemExit("error: no non-empty lines in file")

    engine = build_engine(args.lang, args.threshold)
    policy = get_policy(args.policy) if args.policy else None

    t0 = time.perf_counter()
    results = engine.batch_analyze(texts, args.threshold)
    elapsed = (time.perf_counter() - t0) * 1000

    payloads = [
        _result_payload(r, t, policy, None, None) for r, t in zip(results, texts)
    ]
    toxic_count = sum(1 for r in results if r.is_toxic)

    if args.json:
        print(json.dumps({
            "total": len(texts),
            "toxic_count": toxic_count,
            "total_latency_ms": round(elapsed, 3),
            "results": payloads,
        }, ensure_ascii=False, indent=2))
    else:
        for p in payloads:
            _print_human(p, policy is not None)
        print(f"\n{toxic_count}/{len(texts)} toxic "
              f"in {elapsed:.1f} ms ({len(texts) / (elapsed / 1000):.0f} texts/sec)")
    return 0


def cmd_validate(args) -> int:
    path = Path(args.file)
    ok = True
    try:
        profile = LanguagePackLoader.load_file(path)
    except Exception as exc:
        print(f"INVALID  {path}: {exc}")
        return 1

    print(f"VALID    {path}")
    print(f"  language     : {profile.language_name} ({profile.language_code})")
    print(f"  bad words    : {len(profile.bad_words)}")
    print(f"  context rules: {len(profile.context_rules)}")
    print(f"  categories   : {len(profile.word_categories)}")
    print(f"  min word len : {profile.min_word_length}")
    print(f"  version      : {profile.version}")
    return 0 if ok else 1


def cmd_languages(args) -> int:
    profiles = available_languages()
    if args.json:
        print(json.dumps({
            "languages": [
                {"code": code,
                 "name": getattr(p, "language_name", "?"),
                 "vocabulary_size": len(p.bad_words),
                 "version": getattr(p, "version", "?")}
                for code, p in sorted(profiles.items())
            ]
        }, ensure_ascii=False, indent=2))
        return 0
    print(f"{'code':6} {'language':34} {'words':>7}  version")
    print("-" * 62)
    for code, p in sorted(profiles.items()):
        print(f"{code:6} {getattr(p, 'language_name', '?'):34} "
              f"{len(p.bad_words):>7}  {getattr(p, 'version', '?')}")
    return 0


_BENCH_TEXTS = [
    "hello how are you today",
    "the deployment finished and all tests are green, nice work everyone",
    "you are a fucking idiot and nobody likes you",
    "f4ck this bullsh1t, I'm done",
    "আমি বাংলায় কথা বলি, আজ আবহাওয়া ভালো",
    " ".join("word%d" % i for i in range(120)),
]


def cmd_bench(args) -> int:
    engine = build_engine(args.lang, 0.6)
    iters = args.iterations
    for t in _BENCH_TEXTS:
        engine.analyze(t)  # warm up
    times = []
    t0 = time.perf_counter()
    for _ in range(iters):
        for t in _BENCH_TEXTS:
            s = time.perf_counter()
            engine.analyze(t)
            times.append((time.perf_counter() - s) * 1000)
    total = time.perf_counter() - t0
    times.sort()
    n = len(times)
    print(f"iterations : {iters} x {len(_BENCH_TEXTS)} texts = {n} analyses")
    print(f"total      : {total * 1000:.1f} ms")
    print(f"avg        : {sum(times) / n:.3f} ms")
    print(f"p50        : {times[n // 2]:.3f} ms")
    print(f"p95        : {times[int(n * 0.95)]:.3f} ms")
    print(f"max        : {times[-1]:.3f} ms")
    print(f"throughput : {n / total:.0f} texts/sec")
    return 0


def cmd_eval(args) -> int:
    """Run the labelled evaluation corpus and report precision/recall/F1."""
    from lpte.eval import EVAL_SETS

    profiles = _builtin_profiles()
    if args.lang == "all":
        reports = evaluate_all(profiles, args.threshold)
        if not reports:
            print("No evaluation data available.")
            return 1
        print(f"{'lang':6} {'total':>6} {'acc':>7} {'prec':>7} {'recall':>7} {'f1':>7}  FP/FN")
        print("-" * 62)
        for code, r in sorted(reports.items()):
            print(f"{code:6} {r.total:6} {r.accuracy:7.3f} {r.precision:7.3f} "
                  f"{r.recall:7.3f} {r.f1:7.3f}  {r.false_positives} FP / {r.false_negatives} FN")
        tot = overall(reports)
        print("-" * 62)
        print(f"{'ALL':6} {tot.total:6} {tot.accuracy:7.3f} {tot.precision:7.3f} "
              f"{tot.recall:7.3f} {tot.f1:7.3f}  {tot.false_positives} FP / {tot.false_negatives} FN")

        if args.verbose:
            if tot.false_positive_examples:
                print("\nFalse positives (clean text flagged):")
                for t in tot.false_positive_examples:
                    print(f"  {t!r}")
            if tot.false_negative_examples:
                print("\nFalse negatives (toxic text missed):")
                for t in tot.false_negative_examples:
                    print(f"  {t!r}")

        if args.fail_under is not None and tot.f1 < args.fail_under:
            print(f"\nFAIL: overall F1 {tot.f1:.3f} < required {args.fail_under:.3f}")
            return 1
        return 0

    # single language
    code = args.lang
    profile = profiles.get(code)
    if profile is None:
        print(f"Unknown language: {code}")
        return 1
    cases = EVAL_SETS.get(code)
    if not cases:
        print(f"No evaluation corpus for '{code}'.")
        return 1
    r = evaluate(profile, cases, args.threshold, language_code=code)
    print(f"language  : {code}")
    print(f"total     : {r.total}")
    print(f"accuracy  : {r.accuracy:.3f}")
    print(f"precision : {r.precision:.3f}")
    print(f"recall    : {r.recall:.3f}")
    print(f"f1        : {r.f1:.3f}")
    print(f"TP={r.true_positives} FP={r.false_positives} "
          f"TN={r.true_negatives} FN={r.false_negatives}")
    if args.verbose:
        if r.false_positive_examples:
            print("\nFalse positives:")
            for t in r.false_positive_examples:
                print(f"  {t!r}")
        if r.false_negative_examples:
            print("\nFalse negatives:")
            for t in r.false_negative_examples:
                print(f"  {t!r}")
    if args.fail_under is not None and r.f1 < args.fail_under:
        print(f"\nFAIL: F1 {r.f1:.3f} < required {args.fail_under:.3f}")
        return 1
    return 0


# ─── Parser ───────────────────────────────────────────────────────────────────

def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="lpte",
        description="LPTE — Local Profanity & Toxicity Engine (100% on-device)",
    )
    sub = parser.add_subparsers(dest="command", required=True)

    def add_common(p: argparse.ArgumentParser) -> None:
        p.add_argument("--lang", default="en",
                       help="language code(s): en, bn, bn+en, auto (default: en)")
        p.add_argument("--threshold", type=float, default=0.6,
                       help="confidence threshold 0.0-1.0 (default: 0.6)")
        p.add_argument("--policy", choices=sorted(POLICY_PRESETS),
                       help="apply a moderation policy preset")

    p_an = sub.add_parser("analyze", help="analyze a text string")
    p_an.add_argument("text", help="text to analyze")
    p_an.add_argument("--json", action="store_true", help="emit JSON")
    p_an.add_argument("--sanitize", action="store_true", help="also show masked text")
    p_an.add_argument("--mask", default="*", help="mask character (default: *)")
    add_common(p_an)
    p_an.set_defaults(func=cmd_analyze)

    p_san = sub.add_parser("sanitize", help="mask toxic spans in a text string")
    p_san.add_argument("text")
    p_san.add_argument("--mask", default="*", help="mask character (default: *)")
    p_san.add_argument("--json", action="store_true")
    add_common(p_san)
    p_san.set_defaults(func=cmd_sanitize)

    p_bat = sub.add_parser("batch", help="analyze every non-empty line of a file")
    p_bat.add_argument("file")
    p_bat.add_argument("--json", action="store_true")
    add_common(p_bat)
    p_bat.set_defaults(func=cmd_batch)

    p_val = sub.add_parser("validate", help="validate a JSON language pack")
    p_val.add_argument("file")
    p_val.set_defaults(func=cmd_validate)

    p_lang = sub.add_parser("languages", help="list available language packs")
    p_lang.add_argument("--json", action="store_true")
    p_lang.set_defaults(func=cmd_languages)

    p_eval = sub.add_parser("eval", help="run the labelled accuracy evaluation")
    p_eval.add_argument("--lang", default="all",
                        help="language code, or 'all' (default)")
    p_eval.add_argument("--threshold", type=float, default=0.6)
    p_eval.add_argument("--verbose", action="store_true",
                        help="list every false positive and false negative")
    p_eval.add_argument("--fail-under", type=float, default=None,
                        help="exit non-zero if F1 is below this value (for CI)")
    p_eval.set_defaults(func=cmd_eval)

    p_bench = sub.add_parser("bench", help="run a latency benchmark")
    p_bench.add_argument("--lang", default="en")
    p_bench.add_argument("--iterations", type=int, default=200)
    p_bench.set_defaults(func=cmd_bench)

    return parser


def main(argv: Iterable[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(list(argv) if argv is not None else None)
    return args.func(args)


if __name__ == "__main__":
    sys.exit(main())
