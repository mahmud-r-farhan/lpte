
```
# MiMo Code Agent Workspace Configuration
# Model target: xiaomi/mimo-v2.5-pro (1M Token Windows, Active MoE Routing)

## 1. Project Context & Objectives
- **Project Name:** Open-Source Local Profanity & Toxicity Engine
- **Core Technology:** Google ML Kit (Natural Language NLP Stack) & Cross-Language Tokenization Strategy.
- **Goal:** Build a zero-cost, high-performance, on-device text analyzer capable of parsing, checking, and filtering toxic text structures, initially optimized for the Bengali language, while providing simple data-mapping schemas for immediate localization into any other human language.
- **Constraints:**
  - Strict zero-dependency on remote clouds (100% offline).
  - High execution performance target: Latency under 25ms per text string evaluation.
  - Base pipeline must remain modular for immediate GitHub fork and customization.

## 2. Architecture & Design Paradigms
This architecture prioritizes the **MiMo Compose Workflow**: Think carefully up-front via architectural constraints, then rapidly execute with clean validation testing.

### Memory & State Management Strategy
- **Persistent Project State:** Track language token maps inside isolated lookup models rather than large persistent arrays to preserve KV-cache efficiency.
- **Context Allocation:** Leverage the 1M token context capacity of `mimo-v2.5` to cross-validate multiple dynamic testing sets concurrently during execution blocks.

### Codebase Organization Guidelines
- `/core`: Independent, language-agnostic tokenizers and string segmentation state machines.
- `/languages/bn`: Specific mapping dictionaries, suffix-matching tables, and token-weight vectors tailored for Bengali profanity variants.
- `/platforms`: Platform wrappers (Flutter MethodChannels / native Android wrappers utilizing ML Kit custom token systems).
- `/tests`: Rigorous evaluation metrics ensuring the classifier avoids false positives on phonetically similar, non-toxic words.

## 3. Specialized Task Execution & Prompts

### Phase 1: Engine Pipeline Design
> **Action:** Construct a lightweight string analysis pipeline using clean bit-mask check operations.

```

Execute a strict state machine pattern capable of intercepting incoming strings. Ensure structural decoupling between the token parsing logic and language-specific maps.

```

### Phase 2: Multi-Language Token Mapping Setup
> **Action:** Define an efficient structural format (such as JSON or strict Protocol Buffers) to map offensive root words and context rules.

```

Implement a configuration architecture that lets developers instantly adapt the codebase to a new language by dropping in a single data map file without rewriting engine logic.

```

### Phase 3: Validation Testing Harness
> **Action:** Write comprehensive automated test arrays mimicking common structural bypassing tricks (e.g., character insertions, leetspeak, spaces).

```

Generate exhaustive unit tests covering token edge-cases to guarantee rapid, high-accuracy classification.

```

## 4. Execution Directives for MiMo Engine
- Always toggle `/thinking` visible to evaluate the subagent planning steps before applying changes across multiple modules.
- Prioritize structural safety checks to eliminate memory leaks during string transformations within local environments.
- 
```
