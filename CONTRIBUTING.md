# Contributing to LPTE

The Python core is intentionally zero-dependency. Contributors can add a language or a spelling/context rule in a JSON file, **without editing the classifier**. The project does not claim universal accuracy: report both clean hard negatives and toxic examples for every change.

## Development checks

```bash
python -m pip install -e '.[dev]'
python -m pip install -r website/requirements.txt httpx  # only for optional web tests
pytest -q
ruff check lpte website/app.py
ruff format --check lpte website/app.py
lpte validate languages/
lpte eval --fail-under 0.98
lpte bench --iterations 200   # report hardware, Python version, cache mode
```

`.github/workflows/checks.yml` runs these checks across supported Python versions. `lpte eval` operates on a **small hand-written** regression set; an F1 gate is not evidence that the engine works at that accuracy on your community.

## Add a language or new rule

1. `lpte init-pack <code> --name '<native name>' --word '<reviewed term>' --category insult --scripts Latin --output languages`. Use a lowercase code such as `ur` or `bn-latn`. The command refuses to overwrite an existing file.
2. Curate `bad_words` with real root terms/phrases, `word_categories` for **every** severe term (the default is profanity), `aliases` for romanizations/known evasion forms and `suffix_rules` for inflections. Script hints are optional; if absent they are inferred from vocabulary. Do not include identity terms merely for mentioning a group.
3. Use `context_rules` only for exact benign words/phrases **containing** a bad term (e.g., Japanese `豚` in `豚肉`). An unrelated benign phrase elsewhere will *not* suppress a match. A generic negator list does not provide semantic negation handling.
4. Run `lpte validate languages/<code>_profile.json`, then `lpte analyze '...' --lang <code> --json`. The CLI adds new codes from `./languages` automatically. For explicit overrides of built-ins, use `--packs-dir PATH`; no silent replacement of native stemmers.
5. Collect consented, held-out cases in a private JSONL file (one `{"text": "…", "toxic": true}` or `false` object per line). Run `lpte eval --lang <code> --cases private.jsonl --verbose` and measure category-specific errors with your moderators. Add **non-private**, representative positive and hard-negative regressions to the test suite as appropriate.
6. Submit a PR describing the community/dialect, known ambiguous terms, latency impact, accuracy caveats and tests. Never submit customer chats, access tokens or sensitive material.

When changing an existing *built-in* profile (`lpte/languages/<code>.py`), keep its `languages/<code>_profile.json` vocabulary, categories, aliases and contexts in sync. `tests/test_production_pipeline.py` checks parity, while a native stemmer may still differ from JSON suffix-only stemming. Rebuild engines/restart services after updates; an already compiled engine does not hot-reload rules.

## Bug reports / moderation safety

Provide a minimal reproducible string (redact personal data), selected language/profile, threshold, policy and expected versus actual result. Include obfuscation, script, punctuation and benign context where relevant. Do not rely solely on positive detection tests: false positives and masking the wrong original span are product bugs too. Add a regression case and describe the trade-off before modifying a vocabulary or category.

Changes are MIT-licensed; see [LICENSE](LICENSE).
