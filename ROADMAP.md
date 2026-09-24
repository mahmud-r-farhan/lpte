# LPTE Roadmap

## Current Release — v1.2.0 (shipped)

**Performance**
- [x] `str.translate` bulk character mapping — 7.5× faster on long text
- [x] SymSpell-style delete-1 fuzzy index — O(word length) not O(vocabulary)
- [x] Indexed suffix tables (bucketed by final character)
- [x] Memoized Unicode categories and stemming
- [x] Threshold-free cache keys (one entry serves every threshold)
- [x] Script routing for mixed-script text

**Correctness**
- [x] Context-rule coverage rule — a benign word elsewhere no longer masks a real violation
- [x] Sentence-final `!` no longer turns `ass!` into `assi` (was hiding matches)
- [x] Sanitize masks obfuscated surface forms (`f4ck`, `f.u.c.k`, `f u c k`, `shiiit`)
- [x] Sentence-final `!`/`+` treated as punctuation, not leetspeak
- [x] HTML entity handling — no double-unescaping
- [x] Deterministic `matched_terms` ordering (no set-iteration leakage)

**Real-world features**
- [x] Content categories: `profanity` / `insult` / `sexual` / `slur` / `threat`
- [x] Severity calibration — slurs/threats escalate, swearing/insults capped at HIGH
- [x] Moderation policies with ALLOW / FLAG / MASK / BLOCK actions
- [x] Harm-weighted decisions (same confidence, different consequence)
- [x] Multi-language engine for code-switched chat (Banglish / Hinglish)
- [x] Async API (`analyze_async`, `batch_analyze_async`)
- [x] `lpte` CLI: analyze / sanitize / batch / validate / languages / bench
- [x] 313 tests (from 148)

- [x] Content categories for all 11 packs (was English + Bengali only)
- [x] Labelled evaluation corpus + `lpte eval` with precision/recall/F1
- [x] Fuzzy-match first-character guard (fixes "bonne journée" → "conne")
- [x] Vowel-dropped evasion forms ("fcking", "bstrd", "phuck")
- [x] 373 tests (from 148)

**Language data fixes**
- [x] Bengali: removed bare possessives (`মায়ের` = "mother's") that flagged
      ordinary sentences like "my mother's cooking is lovely"
- [x] Bengali: removed religious identity words (`হিন্দু`, `মুসলিম`)
- [x] Bengali: removed `দুধ` ("milk"); allowlisted benign collocations
- [x] English: replaced bare `kill` with targeted threat phrases
- [x] English: added bullying/insult vocabulary and context rules
- [x] Phrase matching no longer suppressed by an earlier single-word match —
      `"you are such an idiot, go kill yourself"` is a threat, not just an insult
- [x] Benign-object guard: `"I will kill the process"` is sysadmin work, while
      `"I will kill you"` and `"kill the process and you"` stay threats
- [x] Bengali: added the forms actually typed — `বোকাচোদা` compounds, `চোদা`
      conjugations and the colloquial `সালা` spelling (all previously clean)
- [x] 406 tests (from 148)

## Previous Release — v1.0.0

- Core toxicity engine with multi-signal classification
- Bengali and English language packs
- JSON language pack loader
- 10 platform wrappers (Python, Flutter, Android, iOS, React Native, Node.js, Go, Rust, .NET, PHP)
- Web demo with React chat UI
- 148 tests covering bypass tricks and edge cases

---

## v1.1 — Language Expansion

- [ ] Hindi language pack with stemmer
- [ ] Spanish language pack with stemmer
- [ ] Arabic language pack with stemmer
- [ ] Urdu language pack with stemmer
- [ ] French language pack with stemmer
- [ ] Community-contributed language pack guidelines
- [ ] Language pack validation CLI tool

## v1.2 — Detection Improvements

- [ ] Contextual negation detection ("not bad" → clean)
- [x] Multi-word phrase detection
- [x] Weighted scoring per category (tunable thresholds)
- [ ] Confidence calibration with real-world datasets
- [x] Custom user wordlists (allowlist/denylist in ModerationPolicy)
- [ ] Regex pattern support in language packs

## v1.3 — Performance & Scale

- [ ] C extension for hot-path normalization (Cython/Rust FFI)
- [x] Batch analysis API for processing multiple strings
- [x] Async analysis support (Python asyncio)
- [ ] Memory-efficient streaming mode for large texts
- [x] Benchmark CLI (`lpte bench`) and performance regression tests

## v1.4 — Model-Based Detection

- [ ] Optional TFLite/ONNX model integration
- [ ] Training pipeline for custom toxicity classifiers
- [ ] Transfer learning from multilingual models
- [ ] Hybrid mode: rule-based + ML scoring
- [ ] Model versioning and hot-swap support

## v1.5 — Platform & Integration

- [ ] Kotlin Multiplatform (shared core for Android/iOS/JVM)
- [ ] WebAssembly target for browser-based analysis
- [ ] Ruby gem wrapper
- [ ] Java/C# NuGet package publishing
- [ ] Docker image for API deployment
- [ ] Kubernetes Helm chart

## v2.0 — Production Features

- [ ] Rate limiting and abuse prevention
- [ ] Analytics dashboard for moderation metrics
- [ ] Webhook support for real-time content filtering
- [ ] Plugin system for custom detection pipelines
- [x] Multi-language simultaneous detection (MultiLangEngine)
- [ ] Audit logging and compliance reports

---

## Community Goals

- [ ] Reach 100 language packs
- [ ] 1000+ GitHub stars
- [x] Integration guides (see REAL_WORLD_USECASES.md)
- [ ] Integration guides for Discord, Telegram, Slack bots
- [ ] Academic paper on the classification approach
- [ ] Conference talks and workshops

---

## How to Contribute

Pick any unchecked item from this roadmap and open an issue or PR. See [CONTRIBUTING.md](CONTRIBUTING.md) for guidelines.

Priority labels:
- `good-first-issue` — beginner friendly
- `help-wanted` — community contribution needed
- `core` — maintainers only
