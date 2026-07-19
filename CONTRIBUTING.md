# Contributing to LPTE

Thank you for your interest in contributing to the Local Profanity & Toxicity Engine!

## How to Contribute

### Adding a New Language Pack

The easiest way to contribute. Two options:

**Option 1: JSON file (no code required)**

1. Fork the repository
2. Create `languages/<code>_profile.json`
3. Include `bad_words`, `suffix_rules`, and optional `context_rules`
4. Test with the example module
5. Submit a PR

**Option 2: Python implementation (full control)**

1. Create `lpte/languages/<code>.py`
2. Implement a `Stemmer` subclass and `LanguageProfile`
3. Add tests in `tests/test_<code>_stemmer.py`
4. Submit a PR

### Improving Stemmers

If you're a native speaker of a supported language, your expertise is invaluable for:
- Adding missing suffix rules
- Reducing false positives on legitimate words
- Handling dialectal variations

### Bypass Detection

Help us catch new evasion techniques:
- Add test cases in `tests/test_bypass_tricks.py`
- Document the bypass pattern
- Propose detection strategies

### Platform Wrappers

We need help with:
- Native iOS (Swift, no React Native dependency)
- Kotlin Multiplatform
- WebAssembly target
- Ruby, Java, C++ bindings

## Development Setup

```bash
# Clone
git clone https://github.com/lpte/lpte.git
cd lpte

# Install in dev mode
pip install -e ".[dev]"

# Run tests
pytest

# Run example
python example/main.py
```

## Code Style

- Python code follows PEP 8 (enforced by ruff)
- No comments unless the "why" is non-obvious
- Tests must cover both positive and negative cases
- All new features must include tests

## Pull Request Process

1. Create a feature branch from `main`
2. Write tests first (TDD encouraged)
3. Implement the feature
4. Ensure all tests pass (`pytest`)
5. Update README if adding user-facing features
6. Submit PR with clear description

## Language Pack Guidelines

- Root words only (stemmer handles inflections)
- Minimum 20 entries per language for meaningful coverage
- Include common misspellings and phonetic variants
- Document any context rules for ambiguous words
- Test against real-world text samples

## Reporting Issues

When reporting a false positive or false negative:
- Include the exact input text
- Include the language code
- Include the expected vs actual result
- Include any obfuscation patterns used

## License

By contributing, you agree that your contributions will be licensed under the MIT License.
