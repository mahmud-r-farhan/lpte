# LPTE Roadmap

## Current Release — v1.0.0

- Core toxicity engine with multi-signal classification
- Bengali and English language packs
- JSON language pack loader
- 10 platform wrappers (Python, Flutter, Android, iOS, React Native, Node.js, Go, Rust, .NET, PHP)
- Web demo with React chat UI
- 78 tests covering bypass tricks and edge cases

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
- [ ] Multi-word phrase detection
- [ ] Weighted scoring per language (tunable thresholds)
- [ ] Confidence calibration with real-world datasets
- [ ] Custom user wordlists (whitelist/blacklist)
- [ ] Regex pattern support in language packs

## v1.3 — Performance & Scale

- [ ] C extension for hot-path normalization (Cython/Rust FFI)
- [ ] Batch analysis API for processing multiple strings
- [ ] Async analysis support (Python asyncio)
- [ ] Memory-efficient streaming mode for large texts
- [ ] Benchmark suite with standardized datasets

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
- [ ] Multi-language simultaneous detection
- [ ] Audit logging and compliance reports

---

## Community Goals

- [ ] Reach 100 language packs
- [ ] 1000+ GitHub stars
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
