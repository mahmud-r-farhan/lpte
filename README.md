# LPTE — Local Profanity & Toxicity Engine

**Zero-cost, high-performance, on-device text toxicity analysis.**

LPTE is an open-source Python library for detecting and filtering toxic, profane, and offensive text — running entirely on-device with zero cloud dependency. Initially optimized for Bengali, with a plug-and-play language pack system for instant localization.

## Features

- **100% Offline** — No network calls, no cloud APIs, no data leaving the device
- **Sub-millisecond** — ~0.05 ms per chat line, ~4 ms for a long comment (7× faster than v1.0)
- **11 Built-in Languages** — English, Bengali, Chinese, Japanese, Korean, Russian, Spanish, Hindi, French, German, Arabic
- **Bypass-Resistant** — Catches leetspeak, character insertion, zero-width chars, homoglyphs, word splitting
- **Content Categories** — Distinguishes `profanity` / `insult` / `sexual` / `slur` / `threat` so each harm type gets a different response
- **Moderation Policies** — Preset or custom rules that return an action: `ALLOW` / `FLAG` / `MASK` / `BLOCK`
- **Code-Switching** — Handles mixed-script chat (Banglish, Hinglish) via script routing
- **Stemming** — Language-aware suffix, particle, and affix stripping across Latin, Cyrillic, Devanagari, Bengali, Arabic, Hangul, Kana, and CJK
- **Batch, HTML & Async** — Process batches, raw HTML, or await results off the event loop
- **CLI Included** — `lpte analyze | sanitize | batch | validate | languages | bench`
- **Zero Dependencies** — Pure Python, no external packages required
- **Pluggable Architecture** — Drop in a JSON language file, no code changes needed

> Deploying this for real? Read [`REAL_WORLD_USECASES.md`](REAL_WORLD_USECASES.md)
> for integration patterns, tuning procedure, and honest limitations.

## Quick Start (Production Shape)

Detection alone is not a product decision — you need to know what to **do**.
LPTE separates the four concerns:

```python
from lpte import LpteEngine, MultiLangEngine, get_policy
from lpte.languages import EnglishProfile, BengaliProfile

engine = LpteEngine(EnglishProfile)
policy = get_policy("balanced")     # strict | balanced | lenient

result   = engine.analyze("you are a fucking idiot")
decision = policy.decide(result)

print(decision.action.name)   # MASK
print(result.categories)      # ['profanity']

if decision.action.name == "BLOCK":
    reject(result.matched_terms)
elif decision.action.name == "MASK":
    publish(engine.sanitize("you are a fucking idiot"))
    # → "you are a ******* *****"
else:
    publish("you are a fucking idiot")   # ALLOW and FLAG both publish
```

The same confidence produces different actions depending on the harm:

| Message | Confidence | Category | Severity | balanced → | lenient → |
|---|---|---|---|---|---|
| `damn this is good` | 0.80 | profanity | HIGH | MASK | ALLOW |
| `you are so stupid and ugly` | 1.00 | insult | HIGH | MASK | FLAG |
| `you nigger` | 0.80 | slur | CRITICAL | **BLOCK** | **BLOCK** |
| `I will kill you` | 0.70 | threat | CRITICAL | **BLOCK** | **BLOCK** |
| `please kill the background process` | 0.00 | — | NONE | ALLOW | ALLOW |

### Mixed-script chat (Banglish / Hinglish)

```python
engine = MultiLangEngine([BengaliProfile, EnglishProfile])
engine.analyze("তুই একদম idiot")      # → toxic (matched "idiot")
engine.analyze("কুত্তা")               # → toxic (matched "কুত্তা")
engine.analyze("আমি বাংলায় কথা বলি")   # → clean
```

### Command line

```bash
lpte analyze "you are a fucking idiot" --policy balanced
lpte analyze "তুই একদম idiot" --lang bn+en
lpte sanitize "f4ck this bullsh1t"          # → "**** this ********"
lpte batch comments.txt --policy strict --json
lpte validate languages/my_pack.json
lpte bench
```

## Supported Languages

| Code | Language | Native | Built-in Pack | JSON Pack | Stemmer |
|------|----------|--------|---------------|-----------|---------|
| `en` | English | English | `EnglishProfile` | `en_profile.json` | Suffix stemmer |
| `bn` | Bengali | বাংলা | `BengaliProfile` | `bn_profile.json` | Inflection stemmer |
| `zh` | Chinese | 中文 | `ChineseProfile` | `zh_profile.json` | Particle stemmer |
| `ja` | Japanese | 日本語 | `JapaneseProfile` | `ja_profile.json` | Particle & polite stemmer |
| `ko` | Korean | 한국어 | `KoreanProfile` | `ko_profile.json` | Josa & Eomi stemmer |
| `ru` | Russian | Русский | `RussianProfile` | `ru_profile.json` | Cyrillic stemmer |
| `es` | Spanish | Español | `SpanishProfile` | `es_profile.json` | Suffix stemmer |
| `hi` | Hindi | हिन्दी | `HindiProfile` | `hi_profile.json` | Devanagari stemmer |
| `fr` | French | Français | `FrenchProfile` | `fr_profile.json` | Suffix stemmer |
| `de` | German | Deutsch | `GermanProfile` | `de_profile.json` | Suffix stemmer |
| `ar` | Arabic | العربية | `ArabicProfile` | `ar_profile.json` | Affix stemmer |

## Platform Support

| Platform | Language | Package | Status |
|----------|----------|---------|--------|
| **Python** | Python 3.9+ | `pip install lpte` | Core engine |
| **Flutter** | Dart | `lpte_flutter` | Plugin ready |
| **Android** | Kotlin | `lpte-android` | Wrapper ready |
| **iOS** | Swift | `LpteModule` | Bridge ready |
| **React Native** | TypeScript | `lpte-react-native` | Plugin ready |
| **Node.js** | TypeScript | `lpte` (npm) | Module ready |
| **Go** | Go 1.21+ | `github.com/lpte/lpte` | Bindings ready |
| **Rust** | Rust 2021 | `lpte` (crates) | Bindings ready |
| **.NET/C#** | C# / .NET 7+ | `Lpte` (NuGet) | Wrapper ready |
| **PHP** | PHP 8.0+ | `lpte/lpte` (Composer) | Wrapper ready |

All platform wrappers communicate with the Python core engine via subprocess IPC, with optional embedded Python for production deployments.

## Detailed Usage

### Install

```bash
pip install lpte
```

### Python

```python
from lpte import LpteEngine
from lpte.languages import EnglishProfile, ChineseProfile, RussianProfile, BengaliProfile

# English
engine_en = LpteEngine(EnglishProfile)
result = engine_en.analyze("some text here")
if result.is_toxic:
    print(f"Toxic: {result.severity.name} ({result.confidence:.2f})")

# Chinese
engine_zh = LpteEngine(ChineseProfile)
result_zh = engine_zh.analyze("草泥马 傻逼")

# Russian
engine_ru = LpteEngine(RussianProfile)
result_ru = engine_ru.analyze("сука блять")

# Batch analysis
results = engine_en.batch_analyze(["hello world", "you fucking idiot"])

# HTML text analysis
result = engine_en.analyze_html("<b>hello</b> f*ck")

# Sanitize
clean = engine_en.sanitize("you are a bastard")
# → "you are a *******"
```

### Bengali

```python
from lpte import LpteEngine
from lpte.languages import BengaliProfile

engine = LpteEngine(BengaliProfile)
result = engine.analyze("বাংলা টেক্সট")
```

### Custom Language via JSON

```python
from lpte import LpteEngine, LanguagePackLoader

# Load from JSON file
profile = LanguagePackLoader.load_file("es_profile.json")
engine = LpteEngine(profile)

# Or from JSON string
import json
profile = LanguagePackLoader.load_json(json.dumps({
    "language_code": "es",
    "language_name": "Español",
    "bad_words": ["puta", "mierda", "joder"],
    "suffix_rules": ["ción", "mente", "ado", "es", "s"],
}))
engine = LpteEngine(profile)
```

### Flutter

```dart
import 'package:lpte_flutter/lpte_flutter.dart';

final result = await LpteFlutter.analyze(
  'some text',
  languageCode: 'bn',
);

if (result.isToxic) {
  print('Toxic: ${result.severity}');
}
```

### Web Demo

```bash
# Install dependencies
pip install fastapi uvicorn

# Run the web demo
python website/app.py

# Visit http://localhost:8000
```

The web demo includes a chat-like interface where you can test toxicity detection in real-time. Type messages, try bypass tricks (leetspeak, dot separators, word splitting), and see how the engine responds.

## Architecture

```
lpte/
├── lpte/                      # Python package
│   ├── core/
│   │   ├── normalizer.py      # Unicode normalization, leet reversal, zero-width stripping
│   │   ├── tokenizer.py       # Word splitting, n-gram generation
│   │   ├── classifier.py      # Multi-signal scoring (exact, stemmed, concat, fuzzy)
│   │   ├── stemmer.py         # Abstract stemmer interface
│   │   ├── profile.py         # Language profile dataclass
│   │   ├── loader.py          # JSON-based dynamic language loading
│   │   ├── engine.py          # High-level API (analyze, sanitize, batch, async)
│   │   ├── multilang.py       # Code-switched / mixed-script detection
│   │   ├── policy.py          # Moderation actions (ALLOW/FLAG/MASK/BLOCK)
│   │   └── cache.py           # Thread-safe LRU cache
│   ├── cli.py                 # `lpte` command-line interface
│   └── languages/
│       ├── bn.py              # Bengali language pack (stemmer + profile)
│       └── en.py              # English language pack (stemmer + profile)
│
├── languages/                 # JSON language packs (drop-in)
│   ├── bn_profile.json        # Bengali
│   ├── en_profile.json        # English
│   ├── es_profile.json        # Spanish (example)
│   └── hi_profile.json        # Hindi (example)
│
├── platforms/                 # Cross-platform wrappers
│   ├── flutter/               # Flutter plugin (Dart)
│   ├── android/               # Android wrapper (Kotlin)
│   ├── ios/                   # iOS + React Native bridge (Swift)
│   ├── react-native/          # React Native plugin (TypeScript)
│   ├── nodejs/                # Node.js module (TypeScript)
│   ├── go/                    # Go bindings
│   ├── rust/                  # Rust bindings
│   ├── dotnet/                # .NET/C# wrapper
│   └── php/                   # PHP wrapper
│
├── tests/                     # 313 test cases
├── example/                   # Demo application
├── REAL_WORLD_USECASES.md     # Integration patterns, tuning, limitations
└── ROADMAP.md                 # What's next
```

## How It Works

### 1. Normalization Pipeline

Raw text passes through a multi-stage normalization pipeline:

1. **Zero-width character stripping** — Removes invisible Unicode characters
2. **Accent/diacritic stripping** — Normalizes accented characters
3. **Leetspeak reversal** — `0→o`, `1→i`, `3→e`, `4→u`, `@→a`, `$→s`, etc.
4. **Repeated character collapse** — `fuuuuck` → `fu` (2 chars)
5. **Character sanitization** — Strips non-alphanumeric (preserves Bengali)
6. **Case folding** — Lowercase normalization

### 2. Tokenization

Normalized text is split into words, then analyzed at multiple granularities:

- **Word tokens** — Individual words for exact matching
- **Bigrams** — Word pairs for detecting split-word bypasses
- **Trigrams** — Word triples for longer phrase detection
- **Character n-grams** — For fragment-based obfuscation detection

### 3. Multi-Signal Classification

Four independent signals contribute to a weighted score:

| Signal | Weight | Description |
| Signal | Weight | Description |
|--------|--------|-------------|
| Exact match | 1.0 | Direct root-word match |
| Stemmed match | 0.85 | Match after suffix stripping |
| Phrase match | 0.80 | Bigram/trigram vs multi-word vocabulary entries |
| Concatenated match | 0.70 | Split-word bypasses ("f u c k" → "fuck") |
| Fuzzy match | 0.65 | Edit distance ≤ 1 (typo / single-char obfuscation) |

The weighted score is normalized to a 0–1 confidence value. A configurable threshold (default 0.6) determines the binary classification.

### 4. Context Rules (false-positive suppression)

A matched word is **not** reported when either:

1. the matched token *is* a known clean variant (the word `class` for `ass`), or
2. every occurrence of the word in the text lies inside a known-benign
   compound — Japanese `豚` (insult) inside `豚肉` (pork), Bengali `পাগল`
   inside the idiom `পাগলের মতো`, English `kill` inside `kill the process`.

The coverage rule matters: a benign word appearing **elsewhere** in a message
never masks a real violation. `"I passed the exam. you ass!"` is still toxic.

### 5. Categories, Severity and Remediation

Matched terms map to a content category (`profanity`, `insult`, `sexual`,
`slur`, `threat`). Slurs and threats escalate one severity level; swearing and
insults are capped at `HIGH` so two insults never outrank a slur. A
`ModerationPolicy` then turns severity + category into an action:
`ALLOW`, `FLAG`, `MASK` or `BLOCK`.

## Adding a New Language

### Option 1: JSON Language Pack (No Code)

Create a JSON file:

```json
{
  "language_code": "fr",
  "language_name": "Français",
  "bad_words": ["word1", "word2", "word3"],
  "context_rules": {
    "word1": ["benign compound", "another benign phrase"]
  },
  "word_categories": {
    "word1": "profanity",
    "word2": "slur",
    "word3": "threat"
  },
  "min_word_length": 2,
  "suffix_rules": ["tion", "ment", "eur", "eux", "es", "s"]
}
```

Load it:
```python
profile = LanguagePackLoader.load_file("fr_profile.json")
engine = LpteEngine(profile)
```

### Option 2: Python Implementation (Full Control)

```python
from lpte.core.stemmer import Stemmer
from lpte.core.profile import LanguageProfile

class FrenchStemmer(Stemmer):
    def stem(self, word: str) -> str:
        # Your stemming logic here
        return word

FrenchProfile = LanguageProfile(
    language_code="fr",
    language_name="Français",
    bad_words={"word1", "word2"},
    stemmer=FrenchStemmer(),
)
```

## Testing

```bash
# Install dev dependencies
pip install -e ".[dev]"

# Run all tests
pytest

# Run with coverage
pytest --cov=lpte --cov-report=term-missing

# Run specific test suite
pytest tests/test_bypass_tricks.py -v
```

The test suite covers **313 cases** across:
- Bypass trick detection (leetspeak, zero-width, word splitting, etc.)
- False positive prevention (clean words containing profanity substrings)
- Context-rule correctness (benign compounds, unspaced-script compounds)
- Bengali/English stemmer validation
- Content categories and severity calibration
- Moderation policy decisions (allowlist, denylist, per-category thresholds)
- Multi-language / code-switched detection
- Sanitization of obfuscated surface forms
- CLI behaviour
- Performance regression budgets

## Performance

Measured with `lpte bench` on a single core, cache disabled:

| Workload | v1.0 | v1.2 | Change |
|---|---|---|---|
| Chat line (~5 words) | 0.251 ms | **0.050 ms** | 5.0× faster |
| Paragraph (~20 words) | 0.788 ms | **0.139 ms** | 5.7× faster |
| Long comment (200 words) | 27.74 ms | **3.69 ms** | 7.5× faster |
| Obfuscated text | 0.057 ms | **0.024 ms** | 2.4× faster |
| Batch throughput | 4,464/s | **19,492/s** | 4.4× higher |

The worst case is long **clean** text, because every pipeline stage has to run
before the engine can conclude there is nothing there — that is the case the
optimisation work targeted.

How it stays fast:
- Bulk character mapping via `str.translate` (C-level) instead of per-character Python loops
- Memoized Unicode category lookups and stemming results
- Indexed suffix tables (bucketed by final character) instead of linear scans
- SymSpell-style delete-1 index for fuzzy matching — O(word length), not O(vocabulary)
- Threshold-free cache keys, so one cache entry serves every threshold
- Script routing, so mixed-script text only runs the engines that could match

Run `lpte bench` to reproduce on your own hardware.

## Live Demo

**[https://lpte-demo.onrender.com](https://lpte-demo.onrender.com)**

Try the interactive web demo — type messages, test bypass tricks, and see real-time toxicity detection in action.

## Contributing

See [CONTRIBUTING.md](CONTRIBUTING.md) for guidelines.

## License

MIT License — see [LICENSE](LICENSE).

## Credits

Built for the open-source community. Contributions welcome for:
- New language packs
- Improved stemmers
- Platform-specific optimizations
- Bypass detection patterns
