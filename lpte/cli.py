"""LPTE command line: inspect, moderate, validate, benchmark, evaluate.

The core and CLI have no third-party runtime dependencies (Python 3.9+).
Run ``python -m lpte`` or install the ``lpte`` console script.
"""

from __future__ import annotations

import argparse
import json
import sys
import time
from collections.abc import Iterable
from contextlib import nullcontext
from pathlib import Path

from lpte import __version__
from lpte.core.classifier import validate_threshold
from lpte.core.engine import LpteEngine, _check_mask
from lpte.core.loader import LanguagePackLoader
from lpte.core.multilang import MultiLangEngine
from lpte.core.policy import POLICY_PRESETS, ModerationPolicy, get_policy
from lpte.core.profile import CATEGORIES
from lpte.eval import EVAL_SETS, evaluate, evaluate_all, load_cases, overall
from lpte.registry import available_languages, builtin_profiles


def _threshold(value: str) -> float:
    try:
        number = float(value)
        validate_threshold(number)
        return number
    except ValueError as exc:
        raise argparse.ArgumentTypeError(str(exc)) from exc


def _mask(value: str) -> str:
    try:
        _check_mask(value)
        return value
    except ValueError as exc:
        raise argparse.ArgumentTypeError(str(exc)) from exc


def _positive(value: str) -> int:
    try:
        number = int(value)
        if number > 0:
            return number
    except ValueError:
        pass
    raise argparse.ArgumentTypeError("must be a positive integer")


def _profiles(packs_dir: str | None):
    if packs_dir is not None:
        return available_languages(packs_dir, override=True)
    local = Path.cwd() / "languages"
    return available_languages(local if local.is_dir() else None)


def build_engine(
    lang_spec: str,
    threshold: float = 0.6,
    cache_size: int = 512,
    packs_dir: str | None = None,
):
    profiles = _profiles(packs_dir)
    spec = lang_spec.strip().lower()
    if spec in ("auto", "all", "*"):
        codes = list(profiles)
    else:
        codes = list(
            dict.fromkeys(c.strip() for c in spec.replace(",", "+").split("+") if c.strip())
        )
    if not codes:
        raise ValueError("no language selected")
    unknown = set(codes) - profiles.keys()
    if unknown:
        raise ValueError(
            f"unknown language code(s): {', '.join(sorted(unknown))}; run 'lpte languages'"
        )
    if len(codes) == 1:
        return LpteEngine(profiles[codes[0]], threshold, cache_size)
    return MultiLangEngine([profiles[c] for c in codes], threshold, cache_size)


def _payload(
    result,
    text: str,
    policy: ModerationPolicy | None = None,
    sanitized: str | None = None,
    latency_ms: float | None = None,
) -> dict:
    data = {
        "text": text,
        "is_toxic": result.is_toxic,
        "severity": result.severity.name,
        "confidence": round(result.confidence, 4),
        "categories": list(result.categories),
        "matched_terms": list(result.matched_terms),
        "signals": dict(result.signals),
    }
    if result.language:
        data["language"] = result.language
    if sanitized is not None:
        data["sanitized"] = sanitized
    if policy is not None:
        data["decision"] = policy.decide(result, text).as_dict()
    if latency_ms is not None:
        data["latency_ms"] = round(latency_ms, 3)
    return data


def _human(data: dict) -> None:
    print(f"[{'TOXIC' if data['is_toxic'] else 'CLEAN'}] {data['text']}")
    print(f"  severity   : {data['severity']}")
    print(f"  confidence : {data['confidence']:.2f}")
    for key in ("categories", "matched_terms"):
        if data[key]:
            print(f"  {key:10} : {', '.join(data[key])}")
    if "sanitized" in data and data["sanitized"] != data["text"]:
        print(f"  sanitized  : {data['sanitized']}")
    if "decision" in data:
        print(f"  action     : {data['decision']['action']} ({data['decision']['reason']})")
    if "latency_ms" in data:
        print(f"  latency    : {data['latency_ms']:.2f} ms")


def cmd_analyze(args) -> int:
    engine = build_engine(args.lang, args.threshold, packs_dir=args.packs_dir)
    policy = get_policy(args.policy) if args.policy else None
    start = time.perf_counter()
    result = engine.analyze(args.text)
    elapsed = (time.perf_counter() - start) * 1000
    sanitized = (
        engine.sanitize(args.text, mask=args.mask) if args.sanitize and result.is_toxic else None
    )
    data = _payload(result, args.text, policy, sanitized, elapsed)
    if args.json:
        print(json.dumps(data, ensure_ascii=False, indent=2))
    else:
        _human(data)
    return 0


def cmd_sanitize(args) -> int:
    engine = build_engine(args.lang, args.threshold, packs_dir=args.packs_dir)
    output = engine.sanitize(args.text, mask=args.mask)
    if args.json:
        print(
            json.dumps({"original": args.text, "sanitized": output}, ensure_ascii=False, indent=2)
        )
    else:
        print(output)
    return 0


def cmd_batch(args) -> int:
    # Do not load an entire moderation export into RAM; JSON is streamed as
    # one valid document with the summary after the results array.
    with (
        nullcontext(sys.stdin) if args.file == "-" else Path(args.file).open(encoding="utf-8")
    ) as source:
        lines = (line.rstrip("\r\n") for line in source if line.strip())
        first = next(lines, None)
        if first is None:
            raise ValueError("no non-empty lines in file")
        engine = build_engine(args.lang, args.threshold, packs_dir=args.packs_dir)
        policy = get_policy(args.policy) if args.policy else None
        start = time.perf_counter()
        total = toxic = 0
        if args.json:
            print('{"results":[')
        for text in _chain_first(first, lines):
            result = engine.analyze(text)
            data = _payload(result, text, policy)
            if args.json:
                print(("," if total else "") + json.dumps(data, ensure_ascii=False))
            else:
                _human(data)
            total += 1
            toxic += int(result.is_toxic)
        elapsed = (time.perf_counter() - start) * 1000
        if args.json:
            print(f'],"total":{total},"toxic_count":{toxic},"total_latency_ms":{elapsed:.3f}}}')
        else:
            print(
                f"\n{toxic}/{total} toxic in {elapsed:.1f} ms "
                f"({total / elapsed * 1000:.0f} texts/sec)"
                if elapsed
                else f"\n{toxic}/{total} toxic"
            )
    return 0


def _chain_first(first: str, rest: Iterable[str]) -> Iterable[str]:
    yield first
    yield from rest


def cmd_validate(args) -> int:
    path = Path(args.file)
    try:
        if path.is_dir():
            profiles = LanguagePackLoader.load_directory(path)
            if not profiles:
                raise ValueError("no *_profile.json files in directory")
            rows = [(path / f"{code}_profile.json", p) for code, p in sorted(profiles.items())]
        else:
            rows = [(path, LanguagePackLoader.load_file(path))]
        for _, profile in rows:
            LpteEngine(profile, cache_size=0)  # also validates rule compilation
    except (OSError, ValueError, TypeError) as exc:
        print(f"INVALID  {path}: {exc}")
        return 1
    for name, p in rows:
        print(
            f"VALID    {name}  {p.language_name} ({p.language_code}), "
            f"{len(p.bad_words)} terms, {len(p.word_categories)} categories"
        )
    return 0


def cmd_init_pack(args) -> int:
    """Create a valid, minimal draft pack without replacing an existing one."""
    data = {
        "language_code": args.code,
        "language_name": args.name,
        "bad_words": [args.word],
        "word_categories": {args.word: args.category},
        "context_rules": {},
        "aliases": {},
        "suffix_rules": args.suffix or [],
        "scripts": args.scripts or [],
        "min_word_length": 2,
        "version": "0.1.0",
        "description": "Draft pack; add labelled cases before deployment",
    }
    LanguagePackLoader.load_dict(data)  # validate all fields before touching the filesystem
    output = Path(args.output) / f"{args.code}_profile.json"
    output.parent.mkdir(parents=True, exist_ok=True)
    try:
        with output.open("x", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
            f.write("\n")
    except FileExistsError as exc:
        raise ValueError(f"{output} already exists; refusing to overwrite") from exc
    print(f"Created {output}. Add vocabulary/rules, then run 'lpte validate {output}'.")
    return 0


def cmd_languages(args) -> int:
    profiles = _profiles(args.packs_dir)
    rows = [
        {
            "code": code,
            "name": p.language_name,
            "vocabulary_size": len(p.bad_words),
            "version": p.version,
        }
        for code, p in sorted(profiles.items())
    ]
    if args.json:
        print(json.dumps({"languages": rows}, ensure_ascii=False, indent=2))
    else:
        print(f"{'code':10} {'language':34} {'words':>7}  version")
        for row in rows:
            print(f"{row['code']:10} {row['name']:34} {row['vocabulary_size']:7}  {row['version']}")
    return 0


_BENCH_TEXTS = [
    "hello how are you today",
    "the deployment finished and all tests are green, nice work everyone",
    "you are a fucking idiot and nobody likes you",
    "f4ck this bullsh1t, I'm done",
    "আমি বাংলায় কথা বলি, আজ আবহাওয়া ভালো",
    " ".join(f"word{i}" for i in range(200)),
]


def cmd_bench(args) -> int:
    engine = build_engine(
        args.lang, 0.6, cache_size=512 if args.cache else 0, packs_dir=args.packs_dir
    )
    for text in _BENCH_TEXTS:
        engine.analyze(text)
    samples = []
    start = time.perf_counter()
    for _ in range(args.iterations):
        for text in _BENCH_TEXTS:
            s = time.perf_counter()
            engine.analyze(text)
            samples.append((time.perf_counter() - s) * 1000)
    total = time.perf_counter() - start
    samples.sort()
    n = len(samples)
    print(f"mode       : {'warm cache' if args.cache else 'cache disabled'}")
    print(f"iterations : {args.iterations} x {len(_BENCH_TEXTS)} texts = {n} analyses")
    print(f"total      : {total * 1000:.1f} ms")
    print(f"avg        : {sum(samples) / n:.3f} ms")
    print(f"p50        : {samples[n // 2]:.3f} ms")
    print(f"p95        : {samples[int(n * 0.95)]:.3f} ms")
    print(f"max        : {samples[-1]:.3f} ms")
    print(f"throughput : {n / total:.0f} texts/sec")
    return 0


def cmd_eval(args) -> int:
    if args.cases and args.lang == "all":
        raise ValueError("--cases requires --lang CODE")
    profiles = _profiles(args.packs_dir) if args.packs_dir else builtin_profiles()
    if args.lang == "all":
        reports = evaluate_all(profiles, args.threshold)
        print(f"{'lang':6} {'total':>6} {'acc':>7} {'prec':>7} {'recall':>7} {'f1':>7}  FP/FN")
        for code, r in sorted(reports.items()):
            print(
                f"{code:6} {r.total:6} {r.accuracy:7.3f} {r.precision:7.3f} "
                f"{r.recall:7.3f} {r.f1:7.3f}  {r.false_positives} FP / {r.false_negatives} FN"
            )
        report = overall(reports)
        print(
            f"{'ALL':6} {report.total:6} {report.accuracy:7.3f} {report.precision:7.3f} "
            f"{report.recall:7.3f} {report.f1:7.3f}  "
            f"{report.false_positives} FP / {report.false_negatives} FN"
        )
    else:
        profile = profiles.get(args.lang)
        if profile is None:
            raise ValueError(f"unknown language: {args.lang}")
        cases = load_cases(args.cases) if args.cases else EVAL_SETS.get(args.lang)
        if not cases:
            raise ValueError(f"no evaluation corpus for {args.lang}; supply --cases FILE")
        report = evaluate(profile, cases, args.threshold, language_code=args.lang)
        print(
            f"language  : {args.lang}\n"
            f"total     : {report.total}\n"
            f"accuracy  : {report.accuracy:.3f}\n"
            f"precision : {report.precision:.3f}\n"
            f"recall    : {report.recall:.3f}\n"
            f"f1        : {report.f1:.3f}\n"
            f"TP={report.true_positives} FP={report.false_positives} "
            f"TN={report.true_negatives} FN={report.false_negatives}"
        )
    if args.verbose:
        for name, cases in (
            ("False positives", report.false_positive_examples),
            ("False negatives", report.false_negative_examples),
        ):
            if cases:
                print(f"\n{name}:")
                for text in cases:
                    print(f"  {text!r}")
    if args.fail_under is not None and report.f1 < args.fail_under:
        print(f"\nFAIL: F1 {report.f1:.3f} < required {args.fail_under:.3f}")
        return 1
    return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="lpte", description="LPTE — Local Profanity & Toxicity Engine (offline)"
    )
    parser.add_argument("--version", action="version", version=f"lpte {__version__}")
    sub = parser.add_subparsers(dest="command", required=True)

    def common(p, policy: bool = False) -> None:
        p.add_argument("--lang", default="en", help="en, bn+en, auto (default: en)")
        p.add_argument("--threshold", type=_threshold, default=0.6)
        p.add_argument(
            "--packs-dir", help="JSON pack directory; explicitly overrides built-in codes"
        )
        if policy:
            p.add_argument("--policy", choices=sorted(POLICY_PRESETS))

    analyze = sub.add_parser("analyze", help="analyze a string")
    analyze.add_argument("text")
    analyze.add_argument("--json", action="store_true")
    analyze.add_argument("--sanitize", action="store_true")
    analyze.add_argument("--mask", type=_mask, default="*")
    common(analyze, policy=True)
    analyze.set_defaults(func=cmd_analyze)

    sanitize = sub.add_parser("sanitize", help="mask detected surface spans")
    sanitize.add_argument("text")
    sanitize.add_argument("--mask", type=_mask, default="*")
    sanitize.add_argument("--json", action="store_true")
    common(sanitize)
    sanitize.set_defaults(func=cmd_sanitize)

    batch = sub.add_parser("batch", help="stream non-empty lines from a file (or stdin: -)")
    batch.add_argument("file")
    batch.add_argument("--json", action="store_true")
    common(batch, policy=True)
    batch.set_defaults(func=cmd_batch)

    validate = sub.add_parser("validate", help="validate a JSON pack or pack directory")
    validate.add_argument("file")
    validate.set_defaults(func=cmd_validate)

    init_pack = sub.add_parser("init-pack", help="scaffold a validated JSON language pack")
    init_pack.add_argument("code", help="language code (e.g. ur or bn-latn)")
    init_pack.add_argument("--name", required=True, help="native/display language name")
    init_pack.add_argument("--word", required=True, help="one real term to start the vocabulary")
    init_pack.add_argument("--category", choices=sorted(CATEGORIES), default="insult")
    init_pack.add_argument("--scripts", nargs="+", help="Unicode scripts, e.g. Latin Bengali")
    init_pack.add_argument("--suffix", action="append", help="append an inflectional suffix")
    init_pack.add_argument(
        "--output", default="languages", help="pack directory (default: languages)"
    )
    init_pack.set_defaults(func=cmd_init_pack)

    languages = sub.add_parser("languages", help="list available packs")
    languages.add_argument("--json", action="store_true")
    languages.add_argument("--packs-dir")
    languages.set_defaults(func=cmd_languages)

    bench = sub.add_parser("bench", help="benchmark cache-disabled analysis (no network)")
    bench.add_argument("--lang", default="en")
    bench.add_argument("--packs-dir")
    bench.add_argument("--iterations", type=_positive, default=200)
    bench.add_argument("--cache", action="store_true", help="measure a warmed cache instead")
    bench.set_defaults(func=cmd_bench)

    eval_parser = sub.add_parser("eval", help="evaluate labelled cases (regression guard)")
    eval_parser.add_argument("--lang", default="all")
    eval_parser.add_argument("--packs-dir")
    eval_parser.add_argument("--cases", help="JSONL cases: one {text, toxic} object per line")
    eval_parser.add_argument("--threshold", type=_threshold, default=0.6)
    eval_parser.add_argument("--verbose", action="store_true")
    eval_parser.add_argument("--fail-under", type=_threshold)
    eval_parser.set_defaults(func=cmd_eval)
    return parser


def main(argv: Iterable[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(list(argv) if argv is not None else None)
    try:
        return args.func(args)
    except (ValueError, OSError, UnicodeError) as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    sys.exit(main())
