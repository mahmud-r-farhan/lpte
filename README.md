# LPTE — Local Profanity & Toxicity Engine

An **offline, rule-based** Python 3.9+ moderation engine. The core library and CLI have no third-party runtime dependencies. It detects vocabulary and obfuscations; a separate policy determines whether to **ALLOW**, **FLAG**, **MASK** or **BLOCK**. It is not a semantic classifier, a calibrated probability estimate, or a guarantee of safe content.

## What is implemented

- Eleven built-in profiles: English (`en`), Bengali (`bn`), Chinese (`zh`), Japanese (`ja`), Korean (`ko`), Russian (`ru`), Spanish (`es`), Hindi (`hi`), French (`fr`), German (`de`), Arabic (`ar`). A JSON pack can add another language without editing code.
- Exact, inflected, multi-word, alias, split-word and indexed edit-distance-one matches. Unicode script routing for mixed-language messages. Benign-compound rules suppress **only covered occurrences**, not an unrelated violation elsewhere in the message.
- Per-term categories (`profanity`, `insult`, `sexual`, `slur`, `threat`), severity and reusable strict/balanced/lenient moderation policies. Category thresholds are independent of the binary detection threshold.
- Original-surface masking, including `f4ck`, `f.u.c.k`, `f u c k`, `shiiit` and zero-width insertion; threshold-free, bounded, thread-safe evidence cache; batch and asyncio APIs.
- `lpte` CLI (`analyze`, `sanitize`, streaming `batch`, `languages`, `init-pack`, `validate`, `eval`, `bench`) and optional FastAPI demo.

### Install from this checkout

```bash
python -m pip install .                 # core + lpte CLI; Python 3.9+
python -m pip install -e '.[dev]'      # pytest/ruff for contributors
```

For an air-gapped deployment, install from a local wheel; the engine itself never calls the network. The **hosted web demo is not on-device**: its browser sends text to the demo server, and its JavaScript/fonts use CDNs. Do not paste sensitive content there.

## Python: detect → decide → remediate

```python
from lpte import Action, LpteEngine, MultiLangEngine, get_policy
from lpte.languages import EnglishProfile, BengaliProfile

engine = LpteEngine(EnglishProfile, cache_size=2048)  # construct once per worker
policy = get_policy("balanced")  # or "strict" / "lenient"
text = "you are a fucking idiot"
result = engine.analyze(text)
decision = policy.decide(result, text)  # supply text for custom denylist terms

print(result.is_toxic, result.matched_terms, result.categories)
# True ['fuck', 'idiot'] ['profanity', 'insult']
print(decision.action)  # Action.MASK

if decision.action == Action.BLOCK:
    reject_message()
elif decision.action == Action.MASK:
    publish(engine.sanitize(text))  # "you are a ******* *****"
else:
    publish(text)                     # ALLOW or FLAG; enqueue FLAG for review
```

`result.confidence` is a **rule score**, not the probability that a person is abusive. A single exact match scores 0.8; an inflection or multi-word phrase typically scores 0.7. Slurs and targeted threats escalate severity and BLOCK under all presets **when a matching rule fires**. Context and community norms still need review.

| Input | Match category | Balanced | Lenient |
|---|---|---|---|
| `damn this is good` | profanity | MASK | ALLOW |
| `you are so stupid and ugly` | targeted insult | MASK | FLAG |
| `you nigger` | slur | BLOCK | BLOCK |
| `I will kill you` | targeted threat | BLOCK | BLOCK |
| `please kill the background process` | none | ALLOW | ALLOW |

### Code-switched chat, batches, async, HTML

```python
mixed = MultiLangEngine([BengaliProfile, EnglishProfile])
mixed.analyze("তুই একদম idiot").matched_terms  # ['idiot']
mixed.sanitize("কুত্তা and f4ck")             # '****** and ****'
results = mixed.batch_analyze(["hello", "কুত্তা", "f4ck"])
result = await mixed.analyze_async("তুই একদম idiot")
results = await mixed.batch_analyze_async(["hello", "f4ck"])

# Text extraction only, NOT safe HTML rendering/sanitization:
plain_result = LpteEngine(EnglishProfile).analyze_html("<b>f4ck</b>")
```

Script routing skips unrelated packs (e.g., pure Bengali text in `bn+en` does not run English). `auto` loads every available pack; Latin-script packs may all run for Latin text. Do not instantiate new engines per message.

### CLI / CI

```bash
lpte analyze "you are a fucking idiot" --policy balanced --json
lpte analyze "তুই একদম idiot" --lang bn+en --sanitize
lpte sanitize "f4ck this bullsh1t" --mask '#'
lpte batch comments.txt --policy strict --json > report.json  # streamed JSON
cat comments.txt | lpte batch - --lang auto --json > report.json
lpte languages --json
lpte validate languages/                # all *_profile.json files, fail fast
lpte eval --lang en --verbose
lpte eval --fail-under 0.98             # regression gate, NOT external accuracy
lpte bench --iterations 200             # cache disabled by default
lpte bench --iterations 200 --cache     # warmed cache, different workload
```

`batch` reads one non-empty UTF-8 line at a time (memory is bounded by its output stream and engine cache); output JSON contains `results`, `total`, `toxic_count`, and `total_latency_ms`. Errors go to stderr with non-zero exit codes. `--threshold` accepts only finite values in `[0, 1]`; at 0, clean text is **still clean**.

## Data-only language and rule pipeline

```bash
lpte init-pack ur --name 'اردو' --word 'بدتمیز' --category insult \
  --scripts Arabic --output languages
# Edit languages/ur_profile.json to add real vocabulary, categories, aliases,
# benign contexts and suffix_rules; also curate clean + toxic labelled cases.
lpte validate languages/ur_profile.json
lpte analyze 'بدتمیز' --lang ur --json
lpte eval --lang ur --cases my_held_out_cases.jsonl --verbose
```

A pack's relevant fields:

```json
{
  "language_code": "ur",
  "language_name": "اردو",
  "bad_words": ["بدتمیز", "تم بدتمیز ہو"],
  "word_categories": {"بدتمیز": "insult", "تم بدتمیز ہو": "insult"},
  "aliases": {},
  "context_rules": {},
  "suffix_rules": ["وں", "یں"],
  "scripts": ["Arabic"],
  "min_word_length": 2
}
```

Use genuine *normalised* vocabulary and locally reviewed examples; these illustrative phrases are not a shipped Urdu pack. `aliases` maps a variant/romanisation to a term in `bad_words` (English examples: `fcking → fuck`); `context_rules` lists **known benign forms containing a term**, not a generic negation list. `scripts` can be omitted (inferred from words/aliases). The CLI discovers new packs in `./languages`; built-in native stemmers take precedence for duplicate codes. Use `--packs-dir PATH` to explicitly load another directory and override an existing code. In Python, call `LanguagePackLoader.load_file(path)` then `LpteEngine(profile)` or `available_languages(path, override=True)`. For the web demo, set `LPTE_PACKS_DIR` before startup. Changes take effect **after rebuilding engines/restarting the service**; mutating a live profile does not rebuild its indexes.

Validation rejects missing/unknown fields, invalid categories, dangling aliases, bad context data, malformed suffixes/scripts, and duplicate entries. `lpte init-pack` refuses to overwrite an existing file. Add a reviewed JSONL corpus with one `{"text": "…", "toxic": true/false}` per line, then put pack validation, evaluation and tests in CI (see [CONTRIBUTING.md](CONTRIBUTING.md)).

## Evaluation & performance (read before deploying)

The included **83 hand-written examples across 11 languages** are a regression guard, **not** independent validation: they overlap with lexicon development. As of this patch, `lpte eval` reports overall F1 **0.989** with one known English false negative (`no one likes you, go away`). A separate held-out, representative sample from *your* traffic is required to estimate production false-positive rates, harm-category recall or fairness. Keep raw user text on your infrastructure.

`lpte bench --iterations 200` on this workspace (Python 3.11, six fixed strings incl. a 200-word clean text, cache **disabled**) measured ~0.27 ms mean, ~1.24 ms p95 and ~3,666 analyses/sec. This is a local example, **not a service-level guarantee**. Run it on target hardware with realistic messages; warm-cache numbers are much faster but do not represent unseen text. The fuzzy index, Unicode category/stem memoization, suffix buckets for JSON packs, script routing and bounded caches keep cost from scaling with the full dictionary for every token.

See [REAL_WORLD_USECASES.md](REAL_WORLD_USECASES.md) for deployment patterns, rollout/measurement steps and limitations, and [ROADMAP.md](ROADMAP.md) for work still outstanding.

### Optional HTTP demo and existing wrappers

```bash
python -m pip install -r website/requirements.txt
python website/app.py                  # same-origin UI + /api/* on port 8000
```

The HTTP API accepts optional `policy` (`strict`, `balanced`, `lenient`) and `language` (single code, `bn+en`/another pair, or `auto`); request size and threshold are validated. Unknown languages return 400 rather than silently falling back. The bundled UI loads React/Babel/fonts from external CDNs; **the Python core/CLI do not**. For sensitive text, use the in-process API or self-host a privacy-reviewed UI. Platform wrappers under `platforms/` are legacy subprocess examples (not tested for parity with these v1.2 moderation APIs); review and test them before production use.

MIT license: [LICENSE](LICENSE). Contributions: [CONTRIBUTING.md](CONTRIBUTING.md).
