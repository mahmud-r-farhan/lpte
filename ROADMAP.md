# LPTE roadmap

## Python core / CLI — v1.2.0 (this change)

- [x] Multi-signal normalization and classification, phrase/alias matching, prefix-guarded indexed edit-distance-one lookup
- [x] Categories, harm-aware severity, three moderation policy presets, custom policy thresholds and wordlists
- [x] Mixed-script routing (`MultiLangEngine`), bounded threshold-free caches, async and batch APIs
- [x] Sanitization using normalized-to-original spans, including obfuscated and unspaced-script text
- [x] Data-only JSON packs with validation, categories, aliases, suffixes, context rules and Unicode-script hints
- [x] CLI: analyze, sanitize, stream batch, languages, init-pack, validate, bench, eval
- [x] Eleven built-in profiles; JSON versions of their vocabulary and categories checked for parity
- [x] Hand-written evaluation regression guard (83 cases); CI with Python-version tests and pack validation

**Release note:** the existing platform subprocess wrappers and external web UI assets have not been made fully offline or guaranteed to implement the new v1.2 features. The Python core is the tested integration path; the optional FastAPI demo exposes categories/policy as an HTTP service. This is a rule engine, not a calibrated model or a 100%-accurate toxicity classifier.

## Next priorities (not shipped)

1. Collect **held-out, consented, community-specific** evaluation data with separate metrics for slurs/threats and false positives. The checked-in corpus is too small and tuned to prove accuracy.
2. Broaden Banglish/Hinglish/other romanized vocabulary and curate dialect-specific ambiguous terms. `aliases` and `scripts` now make this a data change; coverage still needs native-speaker review.
3. Design safe negation/quotation/context-window rules before automatic suppression, including regression cases where benign and harmful terms coexist.
4. Bring platform wrappers into feature parity with Python APIs; add CI/integration tests for their IPC protocols and permissions.
5. Add opt-in, privacy-preserving rule telemetry; do not log raw chat without a retention and access-control plan.
6. Explore robust model-assisted escalation and production rate limiting **after** validating failure modes and deployment/privacy requirements.

See [REAL_WORLD_USECASES.md](REAL_WORLD_USECASES.md) and [CONTRIBUTING.md](CONTRIBUTING.md) for measurement and pack-maintenance procedures.
