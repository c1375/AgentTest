# Sprint 4 Plan (v3 — Skill-Native, License-Aware, 11 Files)

## TL;DR

S4 closes the **Week-7 deliverable** as a **Claude Code skill** that
generates JUnit 5 tests for Java AI agent code (Spring AI / LangChain4j /
MCP), grounded in **OWASP LLM Top 10 canonical attack payloads**. The
skill is prompt-time augmentation — **no separate engine, no
ANTHROPIC_API_KEY** — the user's existing Claude Code session writes the
tests under instruction from `SKILL.md` + 11 modular rule files.

Real-world eval target: `spring-projects/spring-ai-examples @ 2a6088d`,
file `agentic-patterns/chain-workflow/.../ChainWorkflow.java` (has
unfixed OWASP LLM01 indirect prompt injection at line 121). Compare
**vanilla Claude Code** (locked prompt: 「帮我给 ChainWorkflow.java 写一个测试」)
vs the skill's `/agenttest <file>` output; both test sets run via
`mvn test` against (V_buggy, V_clean) variants.

The pre-pivot engine (FastAPI + analyzer / retrieval / generator /
validator pipeline + synthetic eval harness, ~5000 lines Python + ~200
Java) was deleted in commit `99df6e0`. Pre-pivot code is recoverable
from git history for archeology.

The original v1 plan (4-row synthetic ablation matrix, N=15 fixtures)
and v2 plan (skill + engine dual-track) are **superseded**. v3 reflects
the user's "走 skill 路线 + 全删" decision and the adversarial-review
findings (existing OWASP skills exist, 17-file structure was excessive,
clear-solutions cannot be forked).

---

## Why pivot (S2 → S4 architecture journey)

S1–S3 built a complex engine pipeline assuming "skill = wrapper around
external service". S4 mid-sprint review surfaced four problems:

1. **Self-validation problem.** We wrote samples knowing what bug to
   inject, then tested that we catch it. Closed loop, weak credibility.
2. **Validator gate's classpath was fixture-specific.** Real Spring AI
   user's project compiles against actual Spring AI jars via mvn — our
   stub-only validator was testing a world the user never lives in.
3. **Product surface unclear.** A FastAPI server isn't user-facing.
4. **Skill design philosophy mismatch.** Claude Code skills are
   prompt-time augmentation, not external LLM services. Architecture
   "skill → CLI → engine → Anthropic API" defies skill conventions and
   needs a second API key. **Skill-native** (SKILL.md instructs the
   user's existing Claude Code session) is the right pattern.

v3 adopts skill-native exclusively. Engine deleted. Methodological
rigor is preserved by mechanical clean-vs-buggy mvn test pass/fail —
no human eval, no model-as-judge.

---

## Locked decisions

### 1. Real-world target = ChainWorkflow.java (anchor) + stretch candidates

- **Anchor**: `spring-projects/spring-ai-examples @ 2a6088d` →
  `agentic-patterns/chain-workflow/src/main/java/com/example/agentic/ChainWorkflow.java`
- 131 lines, 1 public method `chain(String userInput)`, 2 constructors, 1 `ChatClient` field
- **Real OWASP LLM01 vulnerability at line 121**: `String.format("{%s}\n {%s}", prompt, response)` —
  user input + intermediate LLM output cycle into next step's prompt
  with no sanitization
- mvn build verified Phase 0: 35s, BUILD SUCCESS, 2 sources compiled, 0 existing tests
- **Stretch (Phase 2 only if anchor passes clean)**: RoutingWorkflow.java
  for LLM06 surface
- **No contortion**: if a risk has no natural OSS file, run N=1

### 2. Eval methodology = mvn test pass/fail with grep-based catch criterion

For each (sample, mode) where `mode ∈ {vanilla, skill}`:

```
V_buggy  = upstream code as-is (LLM01 bug at line 121)
V_clean  = hand-fixed: sanitize() at start of chain() + per loop iter
           (committed separately in experiments/chainworkflow/)

tests A  = Claude Code session output WITH skill (/agenttest invocation)
tests B  = Claude Code session output WITHOUT skill (locked baseline prompt)

Drop A into V_clean's src/test/java → mvn test → expected PASS  (precision)
Drop A into V_buggy's src/test/java → mvn test → expected FAIL  (recall)
Same for B.
```

**Catch criterion**: a (test set, V_buggy) pair is "Catch" iff
- `mvn test` exit != 0 (FAIL/ERROR)
- AND stdout contains an assertion failure matching:
  `(?i)(sanitize|injection|template.?breakout|system\s*:|prompt.?inject)`
- Manual spot-check allowed to **drop** false catches but **not** add new ones

**Precision criterion**: all tests in the set PASS on V_clean.

Headline = (catch ∧ precision) per mode.

**No synthetic safety-net.** v2 kept S3 synthetic eval as backup; v3
deletes the engine and accepts N=1 anecdotal real-world result as the
honest deliverable. The journey + skill design + Phase 2 data + README
narrative are the project's contribution.

### 3. Skill packaging = user-level, 11 files, no fork

- Skill source at `claude-skill/agenttest/`
- Layout:
  ```
  SKILL.md                                   (~150 lines, 7-step orchestrator)
  rules/general/                             (2 files)
    ├── attack-payload-assertions.md
    └── existing-test-awareness.md
  rules/owasp/                               (3 files)
    ├── llm01-prompt-injection.md
    ├── llm02-sensitive-disclosure.md
    └── llm06-excessive-agency.md
  rules/patterns/                            (3 files)
    ├── chain-workflow.md
    ├── tool-handler.md
    └── log-handler.md
  rules/java/                                (2 files)
    ├── chatclient-mocking.md
    └── junit-template.md
  rules/post-generation/                     (1 file)
    └── verify.md
  ```
- **All content original to AgentTest.** `clear-solutions/unit-tests-skills`
  has no LICENSE file (verified 2026-05-06); `anthropics/skills` has no
  formal LICENSE file either. We **cannot fork** either repo's prose or
  code examples. Structural conventions (multi-file rules tree, GWT test
  case format, FORBIDDEN annotations rule, two-phase compile/execute
  verification) are common testing-discipline knowledge and used freely.
- Install via `bin/install-skill.ps1` to `~/.claude/skills/agenttest/`

### 4. Skill triggering = `disable-model-invocation: true` (explicit `/agenttest` only)

Default skill triggering would let Claude auto-invoke when a user says
"write tests for X" — risky for non-Java or non-agent code where the
skill doesn't apply. Explicit-only:
- User types `/agenttest <file>` to invoke
- Skill still appears in `/` menu for discoverability
- Frontmatter: `disable-model-invocation: true`

### 5. Baseline = vanilla Claude Code session (NOT engine endpoint, which no longer exists)

- **Locked baseline prompt (verbatim)**: 「帮我给 ChainWorkflow.java 写一个测试」
- Captured by opening spring-ai-examples in Claude Code (skill installed
  but NOT invoked) and pasting the prompt above
- Output saved verbatim + Claude Code version + model + timestamp →
  `experiments/chainworkflow/baseline-context.md`
- The engine is **deleted**, no `/baseline/synthesize` endpoint exists.
  Vanilla Claude Code session is the only baseline.

### 6. Symmetric tool access (clean ablation)

Both vanilla and skill paths run inside Claude Code (separate sessions),
with identical tool access (Read, Grep, Bash, etc.). The only delta is
whether the skill's instructions inject OWASP grounding. **No tool
asymmetry.** Skill grounding is the only manipulated variable.

### 7. Differentiator = JUnit test generation niche (NOT OWASP novelty)

Per adversarial review, existing skills cover OWASP audit / review:
- [agamm/claude-code-owasp](https://github.com/agamm/claude-code-owasp) —
  OWASP best practices across many languages
- [AgriciDaniel/claude-cybersecurity](https://github.com/AgriciDaniel/claude-cybersecurity) —
  comprehensive cybersec code review

AgentTest fills the adjacent niche:
- **JUnit test generation** (existing skills audit / review, don't generate tests)
- **Java AI agent code** (Spring AI / LangChain4j / MCP — agent-specific,
  not generic)
- **Canonical OWASP attack payload assertions** (the technical
  contribution: assert payload doesn't survive into captured prompt)

**README and SKILL.md explicitly cite related work.** No claim of OWASP
novelty.

### 8. Differentiator framing = "attack-payload assertions" (NOT "invariant tests")

Per adversarial review, "invariant tests vs behavior tests" overlaps
with `clear-solutions/unit-tests-skills`'s `test-behaviors-not-methods`
rule. Our framing is **attack-payload assertions**: tests inject canonical
OWASP attack payloads as input and assert the payload chars don't
survive into captured LLM input / log output / tool side-effect.

This is the **technical contribution** — concrete, narrow, verifiable.
The "behavior vs invariant" framing is too abstract.

---

## Adversarial review findings (2026-05-06, applied to v3)

Three issues with v2 plan, all addressed in v3:

1. **Existing OWASP skills exist on GitHub.** Not a novel claim. v3
   cites related work + scopes differentiator to "JUnit test generation
   niche".
2. **17 files overengineered.** Anthropic skill design guidance: SKILL.md
   should be lean orchestrator, rules loaded on-demand, files split when
   "mutually exclusive paths". v3 sizes down to 11 files.
3. **"Invariant tests" framing duplicated.** clear-solutions has
   `test-behaviors-not-methods` covering similar ground. v3 sharpens to
   "attack-payload assertions".

Plus license discovery: `clear-solutions/unit-tests-skills` and
`anthropics/skills` lack LICENSE files. **All skill content written
fresh, no fork.**

---

## Implementation phases

### Phase 0 — Real-world target lock-in [DONE]

- ✅ `spring-ai-examples` cloned to `E:\桌面\Generative AI\spring-ai-examples`, pinned to `2a6088d`
- ✅ `chain-workflow` mvn build verified (35s, BUILD SUCCESS)
- ✅ ChainWorkflow.java LLM01 vulnerability identified (line 121)

### Phase 0.5 — Cleanup + skill scaffold [DONE]

- ✅ Engine deletion (commit `99df6e0`, 102 files / ~9463 LOC removed)
- ✅ CLAUDE.md rewritten for skill-native (commit `3ff89e9`)
- ✅ Skill framework scaffold (commit `3403a3b`, SKILL.md + 11 stub rules + install script)
- ✅ License check on potential fork sources (no LICENSE in either; all-original)

### Phase 1 — Skill content authoring (~1d, $0)

**Goal**: fill the 11 stub rule files with real, license-clean content,
verified end-to-end by running the skill on ChainWorkflow.java.

Sequenced subtasks (do NOT skip steps):

1. **LLM01 end-to-end chain first (5 files, ~3h)**:
   - `rules/owasp/llm01-prompt-injection.md` — invariant + 5 canonical payloads
   - `rules/patterns/chain-workflow.md` — pattern recognition + multi-step ArgumentCaptor
   - `rules/java/chatclient-mocking.md` — Spring AI ChatClient fluent API mock recipe
   - `rules/java/junit-template.md` — JUnit 5 + Mockito + AssertJ template
   - `rules/post-generation/verify.md` — mvn test-compile + mvn test workflow

2. **End-to-end smoke (~30 min)**:
   - `bin/install-skill.ps1` to install skill
   - Open spring-ai-examples in Claude Code (separate session, NOT this one)
   - `/agenttest agentic-patterns/chain-workflow/src/main/java/com/example/agentic/ChainWorkflow.java`
   - Verify the skill workflow:
     - Reads target + classifies as chain workflow
     - Loads the 5 LLM01-chain rules
     - Outputs Given-When-Then test cases
     - Asks user (AskUserQuestion or text fallback)
     - Generates compileable test class
     - Runs `mvn test-compile` (max 5 retries)
     - Reports per-test outcomes
   - **If anything breaks, fix before continuing** — this validates the architecture

3. **Remaining 6 files (~2h)**:
   - `rules/owasp/llm02-sensitive-disclosure.md`
   - `rules/owasp/llm06-excessive-agency.md`
   - `rules/patterns/tool-handler.md`
   - `rules/patterns/log-handler.md`
   - `rules/general/attack-payload-assertions.md`
   - `rules/general/existing-test-awareness.md`

Tests/validation: smoke run (subtask 2) is the integration test.
Subtask 3 isn't end-to-end-validated — relies on the LLM01 chain proof.

### Phase 2 — Real eval run (~0.5d, $0 LLM cost)

**Goal**: empirical comparison between vanilla and skill paths.

Tasks:

1. **Author `ChainWorkflow_fixed.java`** (V_clean):
   - Add `private static String sanitize(String input)` helper
   - Wrap `userInput` at start of `chain()` + `response` per loop iter
   - Live in `experiments/chainworkflow/` in AgentTest repo
   - Commit separately for diff review

2. **Vanilla Claude Code session** (skill installed but NOT invoked):
   - Open spring-ai-examples in Claude Code
   - Type **locked baseline prompt** verbatim: 「帮我给 ChainWorkflow.java 写一个测试」
   - Save Claude's output verbatim → `experiments/chainworkflow/test_vanilla.java`
   - Record metadata in `experiments/chainworkflow/baseline-context.md`:
     date, Claude Code version, model, full transcript

3. **Skill Claude Code session** (separate, fresh session):
   - `/agenttest agentic-patterns/chain-workflow/.../ChainWorkflow.java`
   - Save final output → `experiments/chainworkflow/test_skill.java`

4. **mvn test on V_buggy** (current upstream state):
   - Drop test_skill.java (renamed to ChainWorkflowAgentGenTest.java) into
     `spring-ai-examples/agentic-patterns/chain-workflow/src/test/java/com/example/agentic/`
   - `cd chain-workflow && ./mvnw test 2>&1 | tee experiments/chainworkflow/mvn-skill-buggy.log`
   - Apply catch criterion (grep)
   - Repeat with test_vanilla.java (separate test class name, separate run)

5. **mvn test on V_clean**:
   - Replace `ChainWorkflow.java` with `ChainWorkflow_fixed.java` (manual cp)
   - Repeat step 4 for both modes (separate logs)
   - Restore upstream

6. **Stretch (only if anchor passed)**: RoutingWorkflow.java for LLM06

7. **Record**: `experiments/realworld-results.md` with table:
   `(sample, mode, V_buggy outcome, V_clean outcome, catch-yes, precision-yes, headline)`

Cost: $0 — vanilla and skill both bill the user's Claude Code subscription.

### Phase 3 — README + project_plan + demo (~1d, $0)

Tasks:

1. **README** rewrite for skill-native:
   - Install (top): clone → `bin\install-skill.ps1`
   - Demo: `/agenttest <file>` walkthrough + sample output
   - Real-world eval results: Phase 2 data + commentary
   - Architecture journey: link to sprint-2/3/4 plans showing engine →
     skill pivot
   - Related work: cite agamm/claude-code-owasp, AgriciDaniel/claude-cybersecurity
   - Rule 4 warning: "generated tests are advisory; review before merging"
   - Locked baseline prompt cited (Chinese + English)
   - Reproducibility note: "real-world demo recorded with Claude Code
     v<X> on 2026-XX-XX"

2. **`docs/project_plan.md` / `.zh.md`** update:
   - These reference the pre-pivot engine architecture. Replace with
     skill-native description. Keep S2/S3 archive content as historical
     "we tried this approach first" narrative.

3. **Demo clip** (3-5 min, light editing OK):
   ```
   00:00  Open spring-ai-examples in Claude Code (skill installed)
   00:15  Vanilla shot: 「帮我给 ChainWorkflow.java 写一个测试」 → save output
   01:30  Skill shot: /agenttest .../ChainWorkflow.java → save output
   02:30  Drop both into src/test/java, run ./mvnw test
   03:30  Side-by-side outcome reveal
   04:00  (Optional) V_clean toggle, re-run mvn test
   ```
   Stored as `docs/demo.mp4` or YouTube unlisted (link in README).

---

## Risk register

| Risk | Likelihood | Impact | Mitigation |
|---|---|---|---|
| Vanilla Claude already writes good OWASP-aware tests; skill adds no measurable value | medium | high | Phase 2 measures empirically. Honest reporting in README either way. The architecture journey + skill design is also part of the contribution. |
| spring-ai-examples mvn build flakes (SNAPSHOT churn) | medium | high | Pinned commit `2a6088d`. Local Maven cache populated after Phase 0 mvn. If build breaks mid-S4, fall back to last-known-good cached state. |
| Skill SKILL.md instructions confuse Claude (skips steps, wrong file loads) | medium | medium | Phase 1 subtask 2 e2e smoke catches this; iterate SKILL.md before continuing to subtask 3. |
| Phase 2 result: skill tied with or worse than vanilla | medium | medium | Honest in README. The "we measured, here's what we found" report is itself the deliverable. No synthetic safety-net to retreat to (engine deleted). |
| Catch criterion grep regex too strict / too loose | low | medium | Manual spot-check failure traces in Phase 2. Tune regex once. Allowed to drop false catches but not add new. |
| Skill auto-triggers on non-applicable code | very low | low | `disable-model-invocation: true` makes `/agenttest` required. Skill cannot auto-invoke. |
| ChainWorkflow.java text blocks crash mvn test | low | medium | Phase 0 already verified mvn build works. mvn handles modern Java (text blocks, records). javalang doesn't, but javalang is no longer used (engine deleted). |
| ~~LICENSE constraint on fork sources~~ | — | — | **Resolved**: clear-solutions / anthropics/skills both have no LICENSE. All content written fresh, no fork. |

---

## Cost + timeline

| Phase | Duration | $ |
|---|---|---|
| 0 — target lock-in (DONE) | 0 | 0 |
| 0.5 — cleanup + scaffold (DONE) | 0 | 0 |
| 1 — skill content authoring | ~1d | 0 |
| 2 — real eval | ~0.5d | 0 |
| 3 — README + project_plan + demo | ~1d | 0 |
| **Total remaining** | **~2.5d** | **$0** |

Skill-native architecture eliminates ALL Anthropic API spend on
AgentTest's side (user's Claude Code subscription covers Phase 2 LLM
calls).

S5 (Week 8) = lightning slides + presentation; no new code.

---

## Pre-pivot artifact disposition

The pre-pivot engine has been **physically deleted from the working
tree** (commit `99df6e0`). Recoverable from git history at any commit
before that hash:

- `git show 4359ac7:engine/configs/owasp.yaml` — the OWASP YAML catalog
- `git show 4359ac7:engine/src/agenttest/generator/prompt.py` — generator prompt
- `git show 4359ac7:engine/eval/results/comparison-2026-05-06T19-26-58.json` — S3 synthetic eval data
- etc.

Pre-pivot relevant commits (chronological):
- `4359ac7` — S4 plan v2 (the now-superseded skill+engine dual-track plan)
- `99df6e0` — engine deletion
- `3ff89e9` — CLAUDE.md rewrite for skill-native
- `3403a3b` — skill framework scaffold

The journey is documented in `docs/plan/sprint-2.md`, `sprint-3.md`,
and the v2 → v3 evolution within `sprint-4.md` (this file).
