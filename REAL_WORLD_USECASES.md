# LPTE — real-world use cases and deployment plan

**Detection is not a product decision.** LPTE matches curated rules, assigns categories and a rule score, then lets your application apply a community-specific policy. It cannot infer intent, consent, quotation, relationship between speakers or the toxicity of a message with no matching words.

## Where it fits

| Setting | Reason to consider LPTE | Deployment caution |
|---|---|---|
| Schools and children's apps | In-process filtering can avoid sending text to an external moderation vendor | A filter alone does not establish regulatory compliance; use human review and privacy controls |
| Forums / comments | Cheap first-pass triage with no per-request model fee | Tune thresholds using labelled traffic; review borderline cases |
| Gaming chat / speech-to-text | Different policy for profanity versus targeted threats/slurs | ASR errors, new slang and reclaimed terms need review |
| Air-gapped services | Python core runs with no network | Install dependencies/artifacts offline; the optional hosted demo is a separate HTTP application |
| Code-switched chat | `MultiLangEngine([BengaliProfile, EnglishProfile])` catches each script | Transliterated slang still needs its own JSON vocabulary/aliases |
| LLM pre-filter | Filter known high-signal content locally, escalate the rest | **Do not assume a fixed percentage of traffic can safely skip model/human review** |

Do not describe Python in-process filtering as inherently "on a mobile device": mobile integrations must include a Python runtime or a reviewed native port. Existing platform wrappers in this repository are examples, not v1.2 feature-parity guarantees.

## Four separate operations

```text
message → analyze() → is_toxic / rule score / matched_terms
                    → categories (slur | threat | insult | sexual | profanity)
                    → policy.decide(result, message) → ALLOW | FLAG | MASK | BLOCK
                    → sanitize(message) only if displaying a MASK decision
```

`Severity` is harm-aware (`slur`/`threat` escalate to CRITICAL; others are capped at HIGH), whereas `confidence` is a **rule score**, not a probability. The caller's analysis threshold (`is_toxic`) and policy's category thresholds are independent: a high global threshold can report `is_toxic=False` while a sufficiently supported slur is still BLOCKed by a policy. Always use `decision.action`, not `is_toxic`, for enforcement.

### Chat: prevent send or mask before publish

```python
from lpte import Action, LpteEngine, get_policy
from lpte.languages import EnglishProfile

engine = LpteEngine(EnglishProfile, cache_size=2048)
policy = get_policy("balanced")

def on_send(text: str) -> tuple[bool, str]:
    result = engine.analyze(text)
    decision = policy.decide(result, text)
    if decision.action == Action.BLOCK:
        return False, "This message needs review."
    if decision.action == Action.MASK:
        return True, engine.sanitize(text)
    if decision.action == Action.FLAG:
        review_queue.push(text, categories=decision.categories)
    return True, text
```

Use `FLAG` when you want a moderator to review without censoring; use `BLOCK` only when you are comfortable with mistakes, appeals and escalation. If your custom policy chooses `MASK` below the binary analysis threshold, lower the threshold passed to `sanitize(text, threshold=…)` to at most `decision.confidence` so it actually masks. With the default engine threshold and presets, no adjustment is needed. Custom allowlists filter **policy decisions**, not detection or `sanitize()` spans: if a policy allows one matched word but masks another in the same message, implement category-aware display rules (or a separate moderation review) before relying on sanitization.

### Mixed script and offline batch

```python
from lpte import MultiLangEngine
from lpte.languages import BengaliProfile, EnglishProfile

mixed = MultiLangEngine([BengaliProfile, EnglishProfile])
mixed.analyze("তুই একদম idiot").matched_terms  # ['idiot']
mixed.analyze("কুত্তা").matched_terms           # ['কুত্তা']
```

The CLI streams a UTF-8 file one line at a time and can be used in offline audits:

```bash
lpte batch exports/comments.txt --lang bn+en --policy balanced --json > report.json
lpte validate languages/  # reject broken or miscategorised JSON packs in CI
lpte eval --lang en --verbose
lpte bench                 # cold cache, local hardware
```

For async services, `await engine.analyze_async(text)` and `await engine.batch_analyze_async(texts)` use worker threads to avoid blocking an event loop; they do not make CPU work disappear. Construct reusable engines at worker startup.

## Rollout and measurement

1. **Shadow mode.** Run decisions on real traffic without enforcing them. Collect aggregate counts and a small, access-controlled sample, subject to retention policy; do not log raw messages by default.
2. **Label a stratified, held-out sample.** Include flagged messages *and* a random sample of unflagged ones; evaluate false positives separately from missed slurs/threats. Ideally include moderators who know the language/community, and review inter-annotator disagreements.
3. **Measure per-harm-category precision/recall.** The bundled hand-written corpus and `lpte eval --fail-under` catch regressions but do **not** estimate real-world rates. Save your own JSONL cases locally (`{"text": "…", "toxic": false}` per line); do not submit private customer messages to a public repo.
4. **Tune policy per community.** Start with a preset, set `category_thresholds`, `mask_above`, `block_above`, allowlist/denylist terms, and review severity/error trade-offs. An unknown denylist term can be caught by `policy.decide(result, original_text)` without adding it to the engine vocabulary.
5. **Introduce enforcement gradually.** Review → mask → block for well-supported harm categories; provide appeals and a rollback switch. Re-measure after language-pack changes or shifts in user slang.

For example:

```python
from lpte import ModerationPolicy

policy = ModerationPolicy(
    category_thresholds={"slur": .6, "threat": .6, "insult": .7, "profanity": .9},
    mask_above=.7,
    block_above=None,
    allowlist={"damn"},
    denylist={"our-brand-slur"},
)
decision = policy.decide(engine.analyze(text), text)
```

## When *not* to rely on it

| Limitation | Consequence | Better path |
|---|---|---|
| Keyword rules, not semantics | "No one likes you here" may not match; a quote of a slur can be blocked | Escalate semantic/borderline content to humans or a separately validated classifier |
| Reclaimed language and dialects | Same term has different meanings across communities | Review decisions with local speakers; tune allowlists and appeals |
| Transliteration, sarcasm, negation | Recall gaps / false positives | Add scoped aliases and labelled cases; do not assume `not bad` is understood |
| Identity/animal/technical words | Ambiguous words can misfire | Prefer targeted phrases and benign-compound rules; avoid labelling identities alone |
| Language coverage and drift | Unsupported scripts/romanized variants go undetected | Add a JSON pack with `word_categories`, `aliases`, and `scripts`; re-evaluate regularly |
| Latency/throughput varies | Cache hits and a local laptop are not production SLOs | Benchmark cache-disabled on *your* text lengths, scripts and host hardware |

An **embedded** Python core gives zero egress if your application does not log/transmit messages. The optional **sidecar/web demo** sends messages over HTTP to its host; use TLS, authentication, quotas and appropriate deployment controls if exposing an API publicly. The repository demo uses CDNs for UI assets and is not an offline front-end. There is currently no shipping C extension, model-based fallback, audit logging or webhook system; [ROADMAP.md](ROADMAP.md) lists future work.
