# LPTE — Local Profanity & Toxicity Engine

**Zero-cost, high-performance, on-device text toxicity analysis.**

LPTE is an open-source Python library for detecting and filtering toxic, profane, and offensive text — running entirely on-device with zero cloud dependency. Initially optimized for Bengali, with a plug-and-play language pack system for instant localization.

## Features

- **100% Offline** — No network calls, no cloud APIs, no data leaving the device
- **<25ms Latency** — Sub-25ms per text string evaluation
- **Multi-Language** — Bengali and English packs included; add any language via JSON
- **Bypass-Resistant** — Catches leetspeak, character insertion, zero-width chars, word splitting
- **Stemming** — Language-aware suffix stripping for inflectional languages
- **Zero Dependencies** — Pure Python, no external packages required
- **Pluggable Architecture** — Drop in a JSON language file, no code changes needed

## Quick Start

### Install

```bash
pip install lpte
```

### Python

```python
from lpte import LpteEngine
from lpte.languages import EnglishProfile

engine = LpteEngine(EnglishProfile)

# Analyze
result = engine.analyze("some text here")
if result.is_toxic:
    print(f"Toxic: {result.severity.name} ({result.confidence:.2f})")

# Quick check
if engine.is_toxic("some text"):
    print("Blocked!")

# Sanitize
clean = engine.sanitize("you are a bastard")
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

## Architecture

```
lpte/
├── lpte/
│   ├── core/
│   │   ├── normalizer.py    # Unicode normalization, leet reversal, zero-width stripping
│   │   ├── tokenizer.py     # Word splitting, n-gram generation
│   │   ├── classifier.py    # Multi-signal scoring (exact, stemmed, ngram, fragment)
│   │   ├── stemmer.py       # Abstract stemmer interface
│   │   ├── profile.py       # Language profile dataclass
│   │   ├── loader.py        # JSON-based dynamic language loading
│   │   └── engine.py        # High-level API
│   └── languages/
│       ├── bn.py            # Bengali language pack
│       └── en.py            # English language pack
│
├── languages/
│   ├── bn_profile.json      # Bengali JSON language pack
│   ├── en_profile.json      # English JSON language pack
│   ├── es_profile.json      # Spanish example pack
│   └── hi_profile.json      # Hindi example pack
│
├── platforms/
│   ├── flutter/             # Flutter plugin (Dart)
│   └── android/             # Android wrapper (Kotlin)
│
├── tests/                   # 40+ test cases
└── example/                 # Demo application
```

## How It Works

### 1. Normalization Pipeline

Raw text passes through a multi-stage normalization pipeline:

1. **Zero-width character stripping** — Removes invisible Unicode characters
2. **Accent/diacritic stripping** — Normalizes accented characters
3. **Leetspeak reversal** — `0→o`, `1→i`, `3→e`, `4→a`, `@→a`, `$→s`, etc.
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
|--------|--------|-------------|
| Exact match | 1.0 | Direct root-word match |
| Stemmed match | 0.85 | Match after suffix stripping |
| N-gram match | 0.7 | Bigram/trigram overlap detection |
| Fragment match | 0.4 | Character-level partial matches |

The weighted score is normalized to a 0–1 confidence value. A configurable threshold (default 0.6) determines the binary classification.

## Adding a New Language

### Option 1: JSON Language Pack (No Code)

Create a JSON file:

```json
{
  "language_code": "fr",
  "language_name": "Français",
  "bad_words": ["word1", "word2", "word3"],
  "context_rules": {
    "word1": ["negator1", "negator2"]
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

The test suite covers:
- **40+ test cases** across all modules
- Bypass trick detection (leetspeak, zero-width, word splitting, etc.)
- False positive prevention (clean words containing profanity substrings)
- Bengali stemmer validation
- English stemmer validation
- JSON language pack loading
- Performance budget verification (<25ms)

## Performance

Target: **<25ms per text evaluation** on standard hardware.

The engine achieves this through:
- HashMap-based O(1) word lookups
- Pure Python with no external dependencies
- Minimal object allocation in hot paths
- Pre-computed suffix tables for stemming

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
