# Sprint 4 Plan (Revised v2 — Pivot to Real-World Eval, Skill-Native)

## TL;DR

S4 closes the **Week-7 deliverable** by pivoting from synthetic-injection
eval on hand-crafted samples to a **real-world eval on Spring AI's
official examples repo (`spring-projects/spring-ai-examples` @
`2a6088d`)**, packaged as a **skill-native Claude Code skill**.

**Critical architectural decision (v2)**: the skill is **prompt-time
augmentation**, not an external LLM service. SKILL.md instructs the
user's existing Claude Code session to:

1. Run our analyzer CLI to identify agent-pattern sites in the target file
2. Run our retrieval CLI to fetch the OWASP catalog entry for each risk
3. Use these as grounding to write the JUnit test class — **the user's
   Claude Code session writes the test, using its own LLM**

**No `ANTHROPIC_API_KEY` needed.** The user's Claude Code session is
the LLM. Our value-add is the structured OWASP grounding + AST-based
site identification, not a separate LLM call.

The Phase 2 eval compares two paths in the same Claude Code session:
- **Vanilla**: user types `「帮我给 ChainWorkflow.java 写一个测试」` (no skill)
- **Skill**: user types `/agenttest ChainWorkflow.java` (skill provides OWASP grounding)

Both produce JUnit test classes; both are dropped into spring-ai-examples'
`src/test/java/` and run via `mvn test` against (V_buggy, V_clean)
variants. **The single delta** between the two paths is whether OWASP
grounding helped Claude write tests that catch the LLM01 vulnerability.

The original S4 plan (4-row synthetic ablation matrix on N=15 fixtures)
is **superseded**. Most of the engine's generator / pipeline / validator
code is **demoted to "synthetic safety-net only"** — see § "Existing
commit disposition" for what stays / demotes / promotes.

---

## Why pivot (mid-S4 course correction)

Four concerns surfaced during S4 sample expansion:

1. **Self-validation problem.** We wrote samples knowing what bug to
   inject, then tested that we catch the bug we knew about. Closed
   loop, weak external credibility.
2. **Validator gate's classpath is fixture-specific.** Our
   runner-helper has 4 hand-written Spring AI stubs. A real Spring AI
   user compiles against actual Spring AI jars via mvn — our validator
   gate is testing a world the user never lives in.
3. **Product surface unclear.** A FastAPI server isn't a user-facing
   artifact. "How would a Spring AI dev actually use this?" had no
   concrete answer until skill packaging.
4. **Skill design philosophy mismatch (v1 → v2).** A Claude Code skill
   is prompt-time augmentation that guides the user's existing LLM
   session, not an external service that calls out to its own LLM.
   Our v1 plan was "skill → CLI → engine → Anthropic API call" which
   defies skill conventions and forces a second API key. v2 picks
   architecture B: skill provides grounding, user's Claude Code
   session writes the test. No second API key, cleaner ablation,
   skill-native.

The pivot trades a 4-row ablation matrix on N=15 synthetic samples for
a smaller real-world eval (N=1, stretch to N=2-3) + a deployable
skill. Methodological rigor is preserved by mechanical clean-vs-buggy
mvn test pass/fail as the ground truth — **no human eval, no
model-as-judge** (CLAUDE.md rule 6 still holds).

---

## Locked decisions

### 1. Real-world target = ChainWorkflow.java (anchor) + stretch candidates

- **Anchor**: `spring-projects/spring-ai-examples` @ commit `2a6088d`
  → `agentic-patterns/chain-workflow/src/main/java/com/example/agentic/ChainWorkflow.java`
  - 131 lines, 1 public method `chain(String userInput)`, 2 constructors, 1 `ChatClient` field
  - **Real OWASP LLM01 vulnerability at line 121**: `String.format("{%s}\n {%s}", prompt, response)` —
    user input + intermediate LLM output cycle into next step's prompt with **no sanitization**
  - mvn build verified Phase 0: 35s, BUILD SUCCESS, 2 sources compiled, 0 existing tests
- **Stretch** (only if Phase 2 anchor goes smoothly):
  - LLM06 candidate: `routing-workflow/RoutingWorkflow.java` — orchestrator picks worker by LLM output
  - LLM02 candidate: TBD — fall back to N=1 if no natural candidate
- **No contortion**: if a risk has no natural OSS file, we run N=1 (LLM01 only)

### 2. Eval methodology = clean/buggy mvn test pass/fail with grep-based catch criterion

For each (sample, mode) where `mode ∈ {vanilla, skill}`:

```
V_buggy  = upstream code as-is (LLM01 bug at line 121)
V_clean  = hand-fixed: sanitize(userInput) at start of chain(),
           sanitize(response) at start of each loop iter
           (committed separately so the diff is reviewable)

tests A  = Claude Code session output WITH skill (analyzer + OWASP grounding injected)
tests B  = Claude Code session output WITHOUT skill (vanilla baseline)

Drop A into V_clean's src/test/java → mvn test → expected PASS  (precision)
Drop A into V_buggy's src/test/java → mvn test → expected FAIL  (recall)
Same for B.
```

**Catch criterion (refined)**: a (test set, V_buggy) pair is "Catch" iff
- `mvn test` exit code != 0 (FAIL or ERROR)
- AND `mvn test` stdout contains at least one assertion-failure line
  matching the OWASP-shape regex:
  `(?i)(sanitize|injection|template.?breakout|system\s*:|prompt.?inject)`
- This filters out "test was just wrong" failures from "test caught the OWASP risk"
- A manual spot-check is allowed to **drop** false catches but not to
  add new catches — keeps the metric mechanical-only

**Precision criterion**: all tests in the set PASS on V_clean.

Headline = (catch ∧ precision) per mode.

### 3. Custom OWASP mutator = skipped

PIT default mutators don't match OWASP-class issues; custom mutators are ~3d
of bytecode work not justified for course timeline. mvn test on clean/buggy
is the only required mechanical metric.

### 4. Safety net = S3 synthetic eval kept at N=6 (no extension to N=15)

The S3 6-sample synthetic comparison (`4/6 vs 4/6` with mutually-exclusive
failure modes) is preserved verbatim as README "Methodology validation".
If Phase 2 produces "tied or worse" real-world numbers, this section
provides the controlled-experiment counterpart.

**No extension to N=15.** The original v1 plan called for 9 new
synthetic samples (~1.7d) to reach N=15. Under v2 architecture, synthetic
eval is the *backup* story, not the headline — investing 1.7d to scale
the backup from N=6 to N=15 is poorly balanced against finishing the
real-world eval and skill packaging. N=6 with the failure-mode
differentiation is sufficient backup signal.

### 5. Skill packaging = user-level, skill-native (architecture B)

- Skill source at `claude-skill/SKILL.md` in AgentTest repo
- `bin/install-skill.ps1` copies to `$env:USERPROFILE\.claude\skills\agenttest\`
- After install, `/agenttest <file>` works in **any** Claude Code project
- **SKILL.md is instructions for the user's Claude Code session, NOT a
  wrapper around our engine's pipeline.** It says: "run analyze CLI,
  run retrieve CLI, use the JSON outputs as grounding to write the test."
- The user's Claude Code LLM does the actual test-writing.

### 6. CLIs = stateless, no LLM (changed from v1)

- `python -m agenttest.analyze <file>` — runs existing analyzer logic,
  prints JSON site list to stdout. **No LLM call.**
- `python -m agenttest.retrieve <risk_id>` — looks up OWASP catalog
  YAML, prints JSON catalog entry to stdout. **No LLM call.**
- **No `agenttest.cli` (the v1 full-pipeline CLI)** — pipeline is used
  internally by synthetic eval, not by skill
- **No `ANTHROPIC_API_KEY` needed by either CLI**

### 7. Baseline = vanilla Claude Code session (NOT engine endpoint)

- **Locked baseline prompt (verbatim)**: 「帮我给 ChainWorkflow.java 写一个测试」
- Captured by opening `spring-ai-examples` in Claude Code without
  invoking the AgentTest skill, pasting the prompt above
- Output saved verbatim + Claude Code version + model + timestamp →
  `experiments/chainworkflow/baseline-context.md`
- The engine's `/baseline/synthesize` endpoint is preserved **only** for
  S3 synthetic-eval reproducibility, not used as the headline baseline

### 8. Symmetric tool access (clean ablation)

Both vanilla and skill paths run inside the same Claude Code session,
with identical tool access (Read, Grep, Bash, etc.). The only delta is
whether the skill's SKILL.md instructions inject OWASP grounding via
analyze + retrieve CLIs. **There is no tool-access asymmetry**. This
makes the comparison a clean ablation: skill grounding is the only
manipulated variable. Architecture A (v1 plan) had asymmetric tools
(skill = one-shot CLI, vanilla = Claude with full tools) — v2 fixes this.

---

## Implementation phases

### Phase 0 — Real-world target lock-in [DONE]

- ✅ `spring-ai-examples` cloned to `E:\桌面\Generative AI\spring-ai-examples`, pinned to `2a6088d`
- ✅ `chain-workflow` mvn build verified (35s, BUILD SUCCESS)
- ✅ ChainWorkflow.java LLM01 vulnerability identified (line 121)

### Phase 1 — Stateless CLIs (~1d, $0)

**Goal**: expose existing analyzer + retrieval as standalone CLIs the skill
can shell out to.

Tasks:

1. **`engine/src/agenttest/analyze.py`** (new module, thin wrapper around
   existing `analyzer/identify.py`):
   - `python -m agenttest.analyze <file>` → JSON `{"sites": [{...}, ...]}`
   - **No LLM call**
   - Argparse + file read + analyzer invocation + json.dumps to stdout
   - ~30 lines

2. **`engine/src/agenttest/retrieve.py`** (new):
   - `python -m agenttest.retrieve <risk_id>` → JSON catalog entry
   - Loads `engine/configs/owasp.yaml`, looks up risk_id
   - Output schema: `{"risk_id", "title", "description", "invariant", "exemplars"}`
   - **No LLM call**
   - ~30 lines

3. **Verify analyzer recognizes ChainWorkflow's ChatClient API** (hidden blocker):
   - `python -m agenttest.analyze <ChainWorkflow.java>`
   - **Expected**: at least 1 prompt_assembler site identified
   - **If 0 sites**: extend analyzer's prompt-assembler rules to recognize
     Spring AI 1.0+ `chatClient.prompt(...).call().content()` fluent API
     (current rules look for `PromptTemplate.create(Map.of(...))` per S2/S3)
   - **This must pass before continuing to Phase 2** — without site identification,
     the skill provides no value over vanilla

4. **Tests**:
   - `tests/test_cli_analyze.py` — invoke CLI on existing fixture
     (RestaurantPromptAssembler), assert JSON shape + non-empty sites
   - `tests/test_cli_retrieve.py` — same for retrieve, assert catalog entry shape

5. **`bin/swap-chainworkflow.ps1`**:
   - Toggle ChainWorkflow.java between V_buggy (upstream) and V_clean
     (our experiments/chainworkflow/ChainWorkflow_fixed.java)
   - Idempotent: knows current state, swaps to other
   - Used by Phase 2 mvn test runs

### Phase 2 — Real eval run (~0.5d, $0)

**Goal**: empirical comparison between vanilla and skill paths in the
same Claude Code project.

Tasks:

1. **Author `ChainWorkflow_fixed.java`** (V_clean):
   - Add `private static String sanitize(String input)` helper (same regex
     as our LLM01 synthetic samples)
   - Wrap `userInput` at start of `chain()` and `response` at end of loop body
   - Live in `experiments/chainworkflow/` in AgentTest repo
   - Commit separately for diff review

2. **Vanilla Claude Code session** (no skill, or skill installed but not invoked):
   - Open `spring-ai-examples` in Claude Code
   - Type **locked baseline prompt**: 「帮我给 ChainWorkflow.java 写一个测试」
   - Save Claude's output verbatim → `experiments/chainworkflow/test_vanilla.java`
   - Record metadata in `experiments/chainworkflow/baseline-context.md`:
     - Date + time, Claude Code version, model, full transcript or screenshot

3. **Skill Claude Code session** (skill installed; install via Phase 3 Task 2):
   - Same project, separate session
   - Type: `/agenttest agentic-patterns/chain-workflow/src/main/java/com/example/agentic/ChainWorkflow.java`
   - Skill follows SKILL.md instructions:
     - Reads the file (Claude's Read tool)
     - Calls `python -m agenttest.analyze <file>` via Bash → parses JSON site list
     - For each unique risk_id in sites, calls `python -m agenttest.retrieve <risk_id>` → OWASP catalog
     - Uses analyzer + retrieval outputs as grounding, writes JUnit 5 test class
     - Prints to conversation, does NOT auto-write
   - Save Claude's output → `experiments/chainworkflow/test_skill.java`

4. **mvn test on V_buggy** (current upstream state):
   - Drop test_skill.java (renamed to ChainWorkflowAgentGenTest.java) into
     `spring-ai-examples/agentic-patterns/chain-workflow/src/test/java/com/example/agentic/`
   - `cd chain-workflow && ./mvnw test 2>&1 | tee mvn-skill-buggy.log`
   - Apply catch criterion: grep stack trace for OWASP-shape regex
   - Repeat with test_vanilla.java (rename, drop, run, log)

5. **mvn test on V_clean**:
   - `bin/swap-chainworkflow.ps1` → swaps ChainWorkflow.java to V_clean
   - Repeat step 4 for both modes (separate logs)
   - `bin/swap-chainworkflow.ps1` → swap back to V_buggy

6. **Stretch (only if anchor passed clean)**: same flow on RoutingWorkflow.java for LLM06

7. **Record results**: `experiments/realworld-results.md` with table:
   `(sample, mode, V_buggy outcome, V_clean outcome, catch-yes, precision-yes, headline)`

**Cost: $0** (vanilla and skill both bill the user's Claude Code session,
not our engine).

### Phase 3 — Skill packaging (~0.5-1d, $0)

**Goal**: `/agenttest <file>` works in any Claude Code project after one install command.

Tasks:

1. **`claude-skill/SKILL.md`**:
   - Frontmatter: name `agenttest`, description tuned for explicit `/agenttest <file>` invocation
     (capability boundary: "Java AI agent code — Spring AI / LangChain4j / MCP")
   - Body: 4-step workflow
     - Step 1: Read the target file
     - Step 2: Run `python -m agenttest.analyze <file>`, parse JSON site list
     - Step 3: For each risk_id, run `python -m agenttest.retrieve <risk_id>`
     - Step 4: Write JUnit 5 test class using analyzer + retrieval as grounding
       - Constraints: only reference symbols visible in target source; use Mockito
         if class has DI-injected interface (e.g., ChatClient); test class name
         `<TargetClass>AgentGenTest`
   - Refusal license: "If 0 sites detected, say 'no agent-pattern sites in
     this file' and stop"
   - Rule 4 reminder: "Print to conversation; do NOT write to disk without
     explicit user confirmation"

2. **`bin/install-skill.ps1`**:
   - Copy `claude-skill/*` to `$env:USERPROFILE\.claude\skills\agenttest\`
   - Idempotent: detect existing install, prompt overwrite
   - Verify `python -m agenttest.analyze --help` succeeds; warn if missing

3. **End-to-end smoke (in fresh Claude Code session, NOT our dev session)**:
   - Install skill via PS1
   - Open spring-ai-examples in Claude Code
   - `/agenttest agentic-patterns/chain-workflow/src/main/java/com/example/agentic/ChainWorkflow.java`
   - Verify Claude actually:
     - Reads the file
     - Calls analyze CLI
     - Calls retrieve CLI for each risk_id
     - Prints a JUnit test class to conversation
   - This is the architecture-B integration test

### Phase 4 — README polish + demo clip (~1d, $0)

Tasks:

1. **README** restructure:
   - **Install** (top): clone → `bin/setup.ps1` → `bin/install-skill.ps1`
   - **Demo**: skill walkthrough on ChainWorkflow.java (vanilla vs skill side-by-side)
   - **Real-world eval results**: Phase 2 data table + commentary
   - **Methodology validation** (safety net): S3 synthetic eval section
   - **Architecture note**: skill is grounding-injection, not external LLM service;
     no second API key needed
   - **Rule 4 warning** prominent: "generated tests are advisory; review before merging"
   - Locked baseline prompt cited in both Chinese and English (international graders)

2. **Demo clip** (3-5 min, soft single take, light editing OK).

   **The demo IS Phase 2's eval execution** — recorded as one Claude Code session
   in spring-ai-examples (with skill installed).

   Sequence (estimated wall-clock with Claude response time):

   ```
   00:00  Open spring-ai-examples in Claude Code (skill already installed)
   00:15  Vanilla shot:
            Type: 「帮我给 ChainWorkflow.java 写一个测试」 (no skill invocation)
            Claude responds (~30-60s think + write)
            Save output → test_vanilla.java
   01:30  Skill shot:
            Type: /agenttest agentic-patterns/.../ChainWorkflow.java
            Claude follows skill: analyze → retrieve → write (~30-60s)
            Save output → test_skill.java
   03:00  Drop both into src/test/java/com/example/agentic/, run ./mvnw test
   03:45  Outcome shown side-by-side: which set caught the LLM01 bug
   04:30  (Optional) Run swap-chainworkflow.ps1 → V_clean, re-run mvn test
            → tests that don't false-positive go green
   ```

   Stored as `docs/demo.mp4` (committed if size permits, ~5-10MB) or YouTube
   unlisted (link in README).

---

## Risk register

| Risk | Likelihood | Impact | Mitigation |
|---|---|---|---|
| **Analyzer doesn't recognize ChainWorkflow's ChatClient API** | medium | **critical** | Phase 1 task 3 verifies before continuing. If 0 sites identified, extend analyzer rules to handle `chatClient.prompt(...).call().content()` fluent API. **Hidden blocker** — without this, skill provides no grounding over vanilla. |
| Vanilla Claude already knows OWASP from training; skill grounding adds nothing | medium | high | Honest in README. Tied result is informative ("Claude already covers this risk class without our help"). Worth documenting either way. |
| spring-ai-examples mvn build flakes (SNAPSHOT churn) | medium | high | Pinned commit `2a6088d`. Local dep cache after Phase 0. If build breaks mid-S4, fall back to last-known-good cached state. |
| Catch criterion grep regex too strict (false-negatives real catches) | low | medium | Manual spot-check of failure traces in Phase 2. Tune regex if found wanting; allowed to drop false catches but not add new ones (mechanical-only constraint). |
| Skill SKILL.md instructions confuse Claude (it doesn't follow steps) | medium | medium | Phase 3 e2e smoke catches this. If Claude skips analyze/retrieve calls, restructure SKILL.md to be more explicit. |
| Phase 2 result: skill tied with or worse than vanilla | medium | medium | Safety net: README emphasizes synthetic-eval methodology validation + S3 two-failure-modes finding. Re-prompt + rerun Phase 2 within budget; tune skill grounding format if helpful. |
| Skill auto-triggers on non-applicable code (e.g., generic Java) | low | low | SKILL.md description scoped to "Java AI agent (Spring AI / LangChain4j / MCP)" + explicit yield language. |

---

## Cost + timeline

| Phase | Duration | $ |
|---|---|---|
| 0 — target lock-in (DONE) | 0 | 0 |
| 1 — stateless CLIs | ~1d | 0 |
| 2 — real eval | ~0.5d | 0 |
| 3 — skill packaging | ~0.5-1d | 0 |
| 4 — README + demo | ~1d | 0 |
| **Total** | **~3-3.5d** | **$0** |

User's Claude Code subscription covers Phase 2's LLM calls (both vanilla and
skill), not our engine. Architecture B eliminates ALL Anthropic API spend
on AgentTest's side.

S4 budget cap: $40 (essentially unspent — synthetic eval reruns from Phase 1.5
preflight or Step 5 reruns are still allowed if needed).

S5 (Week 8) = lightning slides + presentation; no new code.

---

## Existing commit disposition (architecture B)

### Promoted to skill path (main eval)
- `engine/src/agenttest/analyzer/` → exposed as `python -m agenttest.analyze`
- `engine/src/agenttest/retrieval/` → exposed as `python -m agenttest.retrieve`
- `engine/configs/owasp.yaml` → consumed by retrieve CLI

### Demoted to synthetic-only safety net (still runnable, code intact)
- `engine/src/agenttest/generator/` (used by `pipeline.run`)
- `engine/src/agenttest/validator/` (used by `pipeline.run`)
- `engine/src/agenttest/baseline/synthesize.py` (synthetic comparison only)
- `engine/src/agenttest/pipeline.py` (synthetic-only entry point)
- `engine/eval/runner.py` 4-row routing (synthetic ablation; not run in S4)
- `engine/eval/preflight.py` (synthetic samples preflight)

### Per-commit status

| Commit | Subject | Status |
|---|---|---|
| `a77cece` | Step 2: anti-hallucination prompt | demoted (generator system prompt — synthetic-only) |
| `a721f92` | Step 4a: drop-reason category | demoted (validator-gate accounting — synthetic-only) |
| `f9fb513` | Step 3: 4-row ablation harness | demoted (synthetic ablation routing) |
| `82ae81f` | Step 4b: ship-bad-tests rate | demoted (synthetic-only) |
| `c0709b9` | Step 1.5: preflight ship-blocker | demoted (synthetic samples preflight) |
| `1751fc4` | S4 plan v1 | superseded by this v2 plan |
| `05cc580` | LLM01 sample 3 (RagContextBuilder) | **kept for git history only**; not invoked in v2 plan (synthetic stays at N=6) |
| `6c8c7ec` | LLM01 sample 4 (PersonaPromptCustomizer) | **kept for git history only**; not invoked in v2 plan (synthetic stays at N=6) |

**Nothing is deleted.** All synthetic-eval code stays runnable so the README
"Methodology validation" section can be reproduced verbatim.

### Honest framing for README

> *AgentTest's S2-S4 work explored two distinct architectures: an
> end-to-end pipeline that called Anthropic's API to generate tests
> (synthetic-eval safety net), and a skill-native grounding approach
> that injects OWASP context into the user's Claude Code session
> (real-world eval main path). The skill-native approach is the
> recommended user-facing surface — it composes naturally with Claude
> Code, requires no separate API key, and isolates the value-add as
> "structured OWASP grounding". The pipeline approach remains as a
> controlled-experiment counterpart for methodology validation.*
