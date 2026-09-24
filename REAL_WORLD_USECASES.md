# LPTE — Real-World Use Cases & Deployment Plan

Detection is not a product. This document maps LPTE's capabilities onto the
concrete problems teams actually ship, and states plainly where a keyword
engine is the right tool and where it is not.

---

## 1. Who this is for

| Scenario | Why on-device fits | LPTE config |
|---|---|---|
| Schools / kids' apps | COPPA-style data minimisation; can't ship text to a vendor | `policy_strict()` |
| Community forums & comment sections | Cost per API call at scale; latency on every keystroke | `policy_balanced()` |
| Gaming chat (voice-to-text) | Culture tolerates swearing; zero tolerance for slurs | `policy_lenient()` |
| Air-gapped / regulated enterprise | No egress permitted at all | any policy |
| Mobile apps in low-connectivity regions | Must work offline, on-device, mid-range Android | `bn+en` / `hi+en` |
| Pre-filter before an LLM | Cut moderation API spend by filtering the obvious 95% locally | `LpteEngine` first, LLM second |

---

## 2. The four questions a moderator asks

LPTE answers each one as a separate layer, because collapsing them into a
single boolean is what makes naive filters useless.

```
raw text
   │
   ├─ 1. DETECT      → is_toxic, confidence, matched_terms
   ├─ 2. CATEGORISE  → categories: profanity | insult | sexual | slur | threat
   ├─ 3. DECIDE      → action: ALLOW | FLAG | MASK | BLOCK
   └─ 4. REMEDIATE   → sanitize() → censored text for display
```

### Why categories matter — worked example

"damn", "you nigger" and "I will kill you" can all score **0.80 confidence**.
A single threshold treats them identically. LPTE does not:

| Message | Confidence | Category | Severity | balanced → | lenient → |
|---|---|---|---|---|---|
| `damn this is good` | 0.80 | profanity | HIGH | MASK | ALLOW |
| `you are so stupid and ugly` | 1.00 | insult | HIGH | MASK | FLAG |
| `you nigger` | 0.80 | slur | CRITICAL | **BLOCK** | **BLOCK** |
| `I will kill you` | 0.70 | threat | CRITICAL | **BLOCK** | **BLOCK** |
| `please kill the background process` | 0.00 | — | NONE | ALLOW | ALLOW |

Identity attacks and threats are blocked under **every** preset. Swearing is
a cultural setting. That distinction is the whole ball game.

---

## 3. Integration patterns

### 3.1 Chat / messaging — block before send

```python
from lpte import LpteEngine, get_policy
from lpte.languages import EnglishProfile

engine = LpteEngine(EnglishProfile, cache_size=2048)
policy = get_policy("balanced")

def on_message_send(text: str) -> tuple[bool, str]:
    result = engine.analyze(text)
    decision = policy.decide(result)
    if decision.action.name == "BLOCK":
        return False, "Message blocked by community guidelines."
    if decision.action.name == "MASK":
        return True, engine.sanitize(text)   # publish the censored version
    return True, text                        # ALLOW and FLAG both publish
```

### 3.2 Comment moderation queue — triage, don't censor

```python
result = engine.analyze(comment)
decision = policy.decide(result)

if decision.action.name == "FLAG":
    publish(comment)                      # visible immediately
    review_queue.push(comment, reason=decision.reason,
                      categories=decision.categories)
elif decision.action.name == "BLOCK":
    hold(comment)
```

`FLAG` keeps latency at zero for the user while still surfacing the content
to humans — the standard pattern when you don't trust the classifier enough
to auto-censor.

### 3.3 Mixed-script chat (Banglish / Hinglish)

South Asian chat routinely mixes scripts inside one sentence. A single
language pack misses half of every message:

```python
from lpte import MultiLangEngine
from lpte.languages import BengaliProfile, EnglishProfile

engine = MultiLangEngine([BengaliProfile, EnglishProfile])
engine.analyze("তুই একদম idiot")   # → toxic, matched "idiot"
engine.analyze("কুত্তা")            # → toxic, matched "কুত্তা"
engine.analyze("আমি বাংলায় কথা বলি")  # → clean
```

Script routing means a pure-Bengali message only runs the Bengali engine —
you don't pay for all packs on every keystroke.

### 3.4 Async server integration

```python
result = await engine.analyze_async(text)     # CPU work off the event loop
results = await engine.batch_analyze_async(texts)
```

### 3.5 CLI / CI pipelines

```bash
lpte analyze "you are a fucking idiot" --policy balanced
lpte batch   exports/comments.txt --lang en --policy strict --json > report.json
lpte validate languages/my_pack.json     # gate custom packs in CI
lpte bench                               # catch performance regressions
```

---

## 4. Tuning for your community

Start from a preset, then adjust the two knobs that matter:

```python
from lpte import ModerationPolicy

policy = ModerationPolicy(
    category_thresholds={"slur": 0.30, "threat": 0.30,
                         "profanity": 0.75, "insult": 0.60},
    mask_above=0.60,
    block_above=0.90,
    allowlist={"damn"},        # this community is fine with it
    denylist={"our-brand-slur"},  # always block, whatever the score
)
```

**Measure, don't guess.** Extend the labelled corpus in `lpte/eval.py` with
real messages from your traffic, then:

```bash
lpte eval --lang en --verbose    # see exactly what you get wrong
lpte eval --fail-under 0.90      # CI gate against regressions
```

The shipped corpus is a regression guard, not proof of real-world accuracy —
it is small, and the engine has been tuned against it. Its value is that a
vocabulary change can no longer silently break something you fixed before.

**Rollout procedure used in practice:**

1. **Shadow mode (1–2 weeks).** Run `analyze()` on real traffic, log results,
   publish everything. You now have a false-positive rate.
2. **Review the sample.** Have moderators label ~200 flagged + ~200 random
   unflagged messages. This is your only real accuracy number.
3. **Set thresholds from that sample**, not from intuition.
4. **Enable MASK** before BLOCK. Masking is reversible; blocking a paying
   customer's message is not.
5. **Add allowlist entries** for the words your community uses benignly.
6. **Re-measure quarterly.** Slang drifts; a 2024 word list rots by 2026.

---

## 5. Measuring accuracy before you ship

Add your own cases to `lpte/eval.py` — they should come from real moderation
decisions, not from imagination:

```python
ENGLISH: list[tuple[str, bool]] = [
    ("your community's benign jargon", CLEAN),
    ("an actual insult your users type", TOXIC),
]
```

Then `lpte eval --lang en --verbose` lists every false positive and false
negative, which is the fastest way to find out what your pack is missing.
Gate merges on `lpte eval --fail-under <n>`.

Two rules of thumb from operating these systems:

- **A false positive costs more than a false negative** in most communities.
  Blocking an innocent user is visible and memorable; missing one insult is not.
- **Recall on slurs and threats matters more than recall on swearing.** Miss
  "damn" and nothing happens; miss a racial slur and you have an incident.

## 6. Honest limitations

Stating these is part of making this usable in production.

| Limitation | Consequence | Mitigation |
|---|---|---|
| **No semantics** — keyword + stemming, not understanding | "I hate that they call people nigger" (educational quote) is flagged | Allowlist; route context-heavy content to human review |
| **Reclaimed language** — in-group use of slurs is indistinguishable from attacks | Over-blocking within a community | Per-community allowlists; lenient preset |
| **Romanized slang** — "chud" written as "chod" varies wildly | Recall gaps on transliterated abuse | Add local romanized variants to the pack |
| **Sarcasm / negation** — "not bad" is not handled semantically | Occasional false positives | Keep thresholds conservative |
| **Vocabulary drift** — new slang appears constantly | Recall decays over time | Quarterly pack review; JSON packs make this a data change, not a code change |
| **Threats need a target** — "kill" with an inanimate object is ordinary speech | A sysadmin writing "I will kill the process" is blocked as violent | Benign-object allowlist per phrase; anything unlisted still flags, so the failure mode stays on the side of detection |
| **No cross-lingual knowledge** — a slur in a language you haven't packed is invisible | Gaps for long-tail languages | Add a pack; `auto` mode runs all installed ones |

**When to escalate beyond LPTE:** if you need to catch semantically abusive
messages with **no** banned words ("women shouldn't be allowed to…"), keyword
matching cannot help. Use LPTE as a cheap first-pass filter and send the
residual to a classifier or human review.

### Two failures worth internalising

Both were found by writing tests against real chat, not by reasoning about the
code, and both are the kind of bug that survives a demo:

1. **A cheap match hiding an expensive one.** Multi-word phrases — where the
   worst content lives ("kill yourself", "gonna kill you") — were skipped once
   any single word had matched, as a performance shortcut. "you are such an
   idiot, go kill yourself" therefore scored HIGH/profanity on "idiot" and
   never noticed the CRITICAL threat next to it. **A message's severity is
   decided by its worst part**, so the phrase signal now always runs. The
   cheaper fallbacks (concatenation, fuzzy) stay gated; they add recall, not
   severity.
2. **A missing word is invisible.** `বোকাচোদা` — the most common piece of
   abuse in Bengali chat — returned clean, because it is a compound that never
   contains its root as a standalone token. Nobody reported it; it simply
   never fired. This is why `lpte eval` exists and why the corpus is per
   language: **a filter without a labelled corpus is a filter with unknown
   blind spots.**

---

## 7. Deployment topologies

```
A. Embedded (recommended for mobile/desktop)
   App process ──► lpte (in-process)          latency ~0.05 ms, zero egress

B. Sidecar microservice (recommended for web backends)
   API ──► lpte-service (HTTP/gRPC) ──► verdict
   Useful when several services share one policy configuration.

C. Batch / offline audit
   nightly job ──► lpte batch over the day's corpus ──► review queue

D. Hybrid (highest accuracy per dollar)
   traffic ──► LPTE (blocks obvious ~95%, free)
            └─► residual ──► LLM / commercial API (only what's uncertain)
```

Topology D is where the economics are strongest: on-device filtering removes
the bulk of the load before anything is billed or leaves the device.

---

## 8. Performance budget

Measured on this repository (`lpte bench`), single core, no cache:

| Workload | Before | After | Budget |
|---|---|---|---|
| Chat line (~5 words) | 0.146 ms | **0.049 ms** | < 1 ms |
| Paragraph (~20 words) | 0.548 ms | **0.153 ms** | < 2 ms |
| Long comment (200 words) | 25.43 ms | **3.44 ms** | < 15 ms |
| Batch throughput | 4,794/s | **21,734/s** | — |

Worst case is long *clean* text, because every stage must run before the
engine can conclude "nothing here". That is the case the optimisation targeted.

---

## 9. Adding a language (the data-change path)

```json
{
  "language_code": "ur",
  "language_name": "اردو",
  "bad_words": ["..."],
  "context_rules": {"word": ["benign compound", "..."]},
  "word_categories": {"word": "slur"},
  "min_word_length": 2,
  "suffix_rules": ["وں", "یں", "ے"]
}
```

Drop it in `languages/`, validate with `lpte validate languages/ur_profile.json`,
and it is picked up automatically — no code change, no rebuild.

---

## 10. Roadmap priorities (derived from these use cases)

1. ~~**Severity/category coverage for all 11 packs**~~ — shipped in v1.2.0.
   Remaining: raise coverage where it is still under 80% (ar, zh, es).
2. **Romanized slang packs** — Banglish/Hinglish transliterations are common in
   South Asian chat and are the largest remaining recall gap.
3. ~~**Eval harness**~~ — shipped in v1.2.0 (`lpte eval`, 151 labelled cases).
   Next: grow the corpus from real production traffic.
4. **Context windows** — negation and quotation handling to cut false positives.
5. **Pack telemetry** — which rules fire most, to target curation effort.
