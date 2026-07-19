# Contributing to LPTE

Thank you for your interest in contributing to the Local Profanity & Toxicity Engine!

## How to Contribute

### Adding a New Language Pack

The easiest way to contribute. Create a JSON language file:

1. Fork the repository
2. Create `languages/<code>/src/main/resources/<code>_profile.json`
3. Add a `LanguageProfile` implementation in Kotlin
4. Add tests for your language
5. Submit a PR

### Improving Stemmers

If you're a native speaker of a supported language, your expertise is invaluable for:
- Adding missing suffix rules
- Reducing false positives on legitimate words
- Handling dialectal variations

### Bypass Detection

Help us catch new evasion techniques:
- Add test cases in `BypassTrickTest.kt`
- Document the bypass pattern
- Propose detection strategies

### Platform Wrappers

We need help with:
- iOS native implementation (Swift/Objective-C)
- React Native bridge
- Kotlin Multiplatform expansion
- WebAssembly target

## Development Setup

```bash
# Clone
git clone https://github.com/lpte/lpte.git
cd lpte

# Build
./gradlew build

# Test
./gradlew test

# Run example
./gradlew :example:run
```

## Code Style

- Kotlin code follows the official Kotlin coding conventions
- No comments unless the "why" is non-obvious
- Tests must cover both positive and negative cases
- All new features must include tests

## Pull Request Process

1. Create a feature branch from `main`
2. Write tests first (TDD encouraged)
3. Implement the feature
4. Ensure all tests pass
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
