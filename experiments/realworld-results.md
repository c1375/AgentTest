# Phase 2 real-world results — N=3

Empirical comparison of `/agenttest <file>` (skill mode) vs vanilla
Claude Code session (locked baseline prompt) on three real Java AI
agent files in `spring-ai-examples @ 2a6088d`. Each test set runs via
`mvn test` against (V_buggy, V_clean) variants per the methodology
captured in [`docs/project_plan.md`](../docs/project_plan.md) § 5.

## Final headline

| Sample | Pattern | OWASP / ASI risk | skill catch | skill precision | vanilla catch | vanilla precision |
|---|---|---|---|---|---|---|
| **ChainWorkflow.java** | chain workflow | LLM01 direct + indirect | **4 / 5 ✓** | 5 / 5 ✓ | 0 / 5 ✗ | 5 / 5 ✓ |
| **OrchestratorWorkers.java** | iterative-agent (fan-out) | LLM01 + ASI07 + LLM06 / ASI08 | **4 / 4 ✓** | 4 / 4 ✓ | 0 / 7 ✗ | 7 / 7 ✓ |
| **EvaluatorOptimizer.java** | iterative-agent (recursion) | LLM01 + LLM01 indirect + LLM06 / ASI08 | **4 / 4 ✓** | 4 / 4 ✓ | 0 / 7 ✗ | 7 / 7 ✓ |
| **TOTAL** | 3 patterns / 3 ASI families | — | **12 catches** | **13 / 13 PASS on V_clean** | **0 catches** | **19 / 19 PASS on V_clean** |

**Verdict:**
- skill: catch ∧ precision = **TRUE** on every sample
- vanilla: catch ∧ precision = **FALSE** on every sample (catch = 0)

12-0 catch differential across 3 distinct agent patterns; precision
unaffected on both sides (vanilla doesn't false-positive either —
both modes produce well-formed tests, only the framing differs).

## Methodology recap

For each (sample, mode) where `mode ∈ {vanilla, skill}`:

```
V_buggy = upstream code as-is (real OWASP risk present)
V_clean = hand-fixed (sanitize() + bounded loop where applicable)

A = Claude Code session output WITH skill (/agenttest invocation)
B = Claude Code session output WITHOUT skill (locked prompt)

Drop A or B into V_buggy → mvn test → expected FAIL  (catch / recall)
Drop A or B into V_clean → mvn test → expected PASS  (precision)
```

**Catch criterion**: a (test set, V_buggy) pair is "Catch" iff
- mvn test exit ≠ 0
- AND failure messages match
  `(?i)(sanitize|injection|template.?breakout|system\s*:|prompt.?inject)`

All 12 skill catches across 3 samples match the regex (test names +
assertion descriptions reference `sanitize` / `injection` / `template-breakout`
/ `system:` / `prompt`).

**Precision criterion**: every test in the set PASSes on V_clean.

## Per-sample details

### Sample 1 — ChainWorkflow.java (Phase 2 anchor)

Documented in `experiments/chainworkflow/smoke-result.md` (Phase 2
task 2 commit `a5e0f6e`). Headline: skill 4-0 vs vanilla on the
upstream LLM01 vulnerability at line 121 (`String.format("{%s}\n {%s}",
prompt, response)` cycles user input + LLM response into next step's
prompt with no sanitize).

Skill tests covered: template-breakout, OpenAI conversation markers,
Llama instruction tags, indirect injection via response cycling,
sanity (4 LLM calls per `DEFAULT_SYSTEM_PROMPTS` entry).

### Sample 2 — OrchestratorWorkers.java (stretch #1)

**File**: `agentic-patterns/orchestrator-workers/src/main/java/com/example/agentic/OrchestratorWorkers.java`
(203 lines)

**Real upstream OWASP risks**:
- **LLM01**: line 181 `taskDescription` raw-substituted into orchestrator
  prompt's `task` parameter (no sanitize)
- **ASI07** (insecure inter-agent communication): orchestrator-emitted
  `task.type()` and `task.description()` raw-substituted into worker prompts
- **LLM06 / ASI08** (cascading failures): line 189 streams over LLM-controlled
  `tasks` list with no upper bound — a runaway/poisoned orchestrator
  response can spawn arbitrary worker LLM calls

**V_clean v2 fix** (`experiments/orchestratorworkers/OrchestratorWorkers_fixed.java`):
- `sanitize()` helper (same family as `ChainWorkflow_fixed.java`'s) applied to
  `taskDescription` before the orchestrator-prompt `param("task", …)`
- `sanitize()` applied to `task.type()` / `task.description()` before each
  worker-prompt `param(…)`
- `MAX_WORKERS = 10` cap on `tasks` list (silent truncate via `subList`)

**Skill tests** (`experiments/orchestratorworkers/test_skill.java`):

| # | Test | V_buggy | V_clean |
|---|---|---|---|
| 1 | `process_userInputContainsTemplateBreakout_orchestratorParamDoesNotLeakPayload` | FAIL ✓ | PASS |
| 2 | `process_orchestratorReturnsPoisonedTaskFields_workerParamsAreSanitized` | FAIL ✓ | PASS |
| 3 | `process_orchestratorReturns1000Tasks_workerCountIsCappedAtReasonableBound` | FAIL ✓ | PASS |
| 4 | `process_orchestratorReturnsLlamaInstInjection_workerParamsDoNotLeakInstTags` | FAIL ✓ | PASS |

**Vanilla tests** (`experiments/orchestratorworkers/test_vanilla.java`): 7
behavior-match tests — constructor null/empty checks (3),
`processOrchestratesAndAggregatesWorkerOutputs` (asserts exact response
list), `processHandlesEmptyWorkerTaskList`, `processRejectsEmptyTaskDescription`,
`customPromptsArePassedToChatClient`. All 7 PASS on both V_buggy and
V_clean — catch = 0, precision intact.

### Sample 3 — EvaluatorOptimizer.java (stretch #2)

**File**: `agentic-patterns/evaluator-optimizer/src/main/java/com/example/agentic/EvaluatorOptimizer.java`
(291 lines)

**Real upstream OWASP risks**:
- **LLM01**: line 250 user `task` raw-substituted into generator prompt
- **LLM01 indirect / ASI04**: line 233 evaluator's `feedback` raw-appended to
  next-iteration `context` — a poisoned evaluator response re-injects
  instructions into the generator
- **LLM06 / ASI08**: lines 212–235 are an unbounded recursive loop;
  the only exit is `evaluation == PASS`. A perpetually-NEEDS_IMPROVEMENT
  evaluator triggers `StackOverflowError`.

**V_clean v2 fix** (`experiments/evaluatoroptimizer/EvaluatorOptimizer_fixed.java`):
- `sanitize()` applied to user `task` at the entry to `loop(String)` so all
  generator/evaluator calls see the cleaned form
- `sanitize()` applied to `evaluationResponse.feedback()` before appending
  to `newContext` (closes indirect-injection)
- `MAX_ITERATIONS = 10` threaded through new `int iteration` parameter on
  the private recursive `loop`; throws `IllegalStateException` with message
  containing `"max"` when exceeded (skill test wraps in try/catch per
  `rules/patterns/iterative-agent.md` Invariant 1 Option A)

**Skill tests** (`experiments/evaluatoroptimizer/test_skill.java`):

| # | Test | V_buggy | V_clean |
|---|---|---|---|
| 1 | `loop_userTaskContainsTemplateBreakout_taskParamDoesNotLeakPayload` | FAIL ✓ | PASS |
| 2 | `loop_userTaskContainsImStartMarker_taskParamDoesNotLeakMarkers` | FAIL ✓ | PASS |
| 3 | `loop_evaluatorFeedbackContainsInjection_secondGenerationContextIsClean` | FAIL ✓ | PASS |
| 4 | `loop_evaluatorNeverReturnsPass_terminatesWithinDocumentedBound` | FAIL ✓ | PASS |

**Vanilla tests** (`experiments/evaluatoroptimizer/test_vanilla.java`): 7
behavior-match tests — constructor null/empty checks (3),
`loopReturnsImmediatelyWhenFirstEvaluationPasses`, `loopIteratesUntilEvaluationPasses`
(asserts exact 3-iteration sequence), `loopTreatsFailAsRetryableLikeNeedsImprovement`,
`customPromptsArePassedToChatClient`. All 7 PASS on both V_buggy and V_clean.

## Cross-cutting findings

### Finding 1: vanilla has the technical chops, lacks the framing

Across all three samples, vanilla Claude wrote technically competent
Spring AI tests:
- Correct fluent-API mocks (`ChatClient.ChatClientRequestSpec`,
  `CallResponseSpec`, `PromptUserSpec`)
- Correct use of `ArgumentCaptor.getAllValues()` (ChainWorkflow test #3)
- Correct usage of `Consumer<PromptUserSpec>` matchers
- Correct invocation-count `verify(times(N))` patterns

But every vanilla test was **behavior-match** ("the code does X"), not
**invariant** ("the code SHOULD do Y regardless of current state"). The
delta is purely framing — the skill instructs Claude to think
adversarially about LLM-controlled inputs/outputs; vanilla defaults to
asserting present behavior.

### Finding 2: indirect-injection coverage is consistent across patterns

All three skill outputs caught the indirect-injection surface specific
to each pattern:
- ChainWorkflow: LLM response → next step's prompt (test #4)
- OrchestratorWorkers: orchestrator's `task` fields → worker prompts
  (test #2 ASI07, test #4 Llama tags)
- EvaluatorOptimizer: evaluator feedback → next-iteration context (test #3)

The skill's `rules/owasp/llm01-prompt-injection.md` documents this as
the highest-leverage attack surface in agent code. The N=3 evidence
suggests the skill teaches Claude to recognize the surface across
distinct pattern shapes (response-cycling, fan-out, recursion).

### Finding 3: V_clean scope must match catch scope (methodology lesson)

V_clean v1 (initial attempt) for the two stretch samples fixed only
the bounded-loop OWASP risk (`LLM06 / ASI08`), reasoning that this was
the "stretch-specific" risk. The skill, however, also caught LLM01
prompt-injection variants in both samples — so V_clean v1 had
precision = 0/4 (skill tests for sanitize were testing for sanitize()
behavior V_clean v1 didn't have).

**Lesson**: V_clean must be a *comprehensive* fix for every OWASP
risk the skill identifies, not just the headline risk. A real
engineer reading skill output would fix all flagged risks; an
incomplete V_clean is a V_clean defect, not a skill defect.

V_clean v2 added `sanitize()` to user inputs and orchestrator/evaluator
LLM outputs across both stretch samples. precision climbed to 4/4 on
both. This is documented in the V_clean v1→v2 commit history.

### Finding 4: skill test patterns vary in throw-handling discipline

Two iterative-agent skill rule patterns differ in whether they
accommodate a throwing V_clean fix:

- `iterative-agent.md` Invariant 1 (bounded total iterations) — explicitly
  allows Option A throw via `assertThatThrownBy(...).hasMessageContaining("max")`.
  EO test 4 followed this with try/catch. ✓
- `iterative-agent.md` Invariant 2 (LLM-determined fan-out cap) — uses
  bare `verify(atMost(...))` with no try/catch. OW test 3 followed
  this — V_clean v1's `throw` here caused test 3 to ERROR.

This is a **skill rule consistency gap** worth documenting (see
"Future skill iterations" below). For Phase 2 we worked around it by
using `subList` truncate-not-throw in OrchestratorWorkers V_clean v2.
Both throw and truncate are defensible engineering — the skill rule
should accommodate both.

## Limitations

- **N=3, single Claude Code build, single point in time**. The
  4-0 / 4-0 / 4-0 result is an existence proof — "this differential
  is achievable across pattern variants" — not a benchmark over a
  large sample distribution.
- **Self-selection on samples**. We picked iterative-agent variants
  (orchestrator-workers + evaluator-optimizer) precisely because the
  skill has unvalidated rules for them. Other agent patterns
  (tool-handler, log-handler, MCP server) are untested in Phase 2.
- **V_clean is hand-authored after seeing the skill rule**, not blind.
  The methodological guard is that V_clean is authored without
  reading the *specific test outputs* — only the OWASP risk class. The
  V_clean v1→v2 evolution shows the boundary: v1 was authored from the
  rule, v2 was a comprehensive fix when v1 didn't satisfy precision.
- **Non-throwing V_clean is a methodological choice** for OW
  (truncate-not-throw to match skill test pattern). A defensive
  production fix could legitimately throw; the choice doesn't change
  the catch outcome.
- **Catch-criterion regex applied with manual spot-check** for false
  positives (none found). Allowed to drop false catches but not add
  new ones (per sprint-4.md methodology).

## Reproducibility

| Component | Pin / version |
|---|---|
| `spring-ai-examples` commit | `2a6088db3d18d5fa6fc208b12adf1172d22f77fd` |
| AgentTest skill commit | `b5115a2` (V_clean v1) → V_clean v2 in this commit |
| Java | OpenJDK 17+ on PATH |
| Maven wrapper | `./mvnw` (3.9.x bundled) |
| Anchor commit (Phase 2 anchor) | `a5e0f6e` (`smoke-result.md` headline) |
| Stretch commit (this) | TBD on commit |

Reproduce a single sample's run:

```pwsh
# Anchor or stretch — same shape
$dir = "E:\桌面\Generative AI\spring-ai-examples\agentic-patterns\<sample>"
$src = "$dir\src\main\java\com\example\agentic\<Sample>.java"
$test_dir = "$dir\src\test\java\com\example\agentic"
$clean = "E:\桌面\Generative AI\AgentTest\experiments\<sample>\<Sample>_fixed.java"

# 1. drop test source (rename to match class name in file)
Copy-Item "experiments\<sample>\test_skill.java" "$test_dir\<Sample>AgentGenTest.java"

# 2. V_buggy run
Push-Location $dir
.\mvnw.cmd -B -ntp clean test "-Dtest=<Sample>AgentGenTest"   # expect FAIL
Pop-Location

# 3. swap to V_clean
Copy-Item $clean $src -Force

# 4. V_clean run
Push-Location $dir
.\mvnw.cmd -B -ntp clean test "-Dtest=<Sample>AgentGenTest"   # expect PASS
Pop-Location

# 5. restore upstream
Push-Location "E:\桌面\Generative AI\spring-ai-examples"
git checkout -- "agentic-patterns/<sample>/src/main/java/com/example/agentic/<Sample>.java"
Pop-Location
```

Each `mvn` run takes 5–15 s on warm Maven cache.

## Future skill iterations (out of scope for Phase 2)

- Reconcile `iterative-agent.md` Invariant 1 vs Invariant 2 throw-vs-truncate
  expectation — both should accept either V_clean style.
- Validate `tool-handler` and `log-handler` rule chains end-to-end
  (not done in Phase 2; sprint-4.md defers tool-handler to "future
  stretch", log-handler has no clean OSS target in spring-ai-examples).
- Expand to non-Spring-AI Java agent code (LangChain4j, raw MCP servers).

These are deliberately deferred — the Week-7 deliverable is the skill
itself plus the N=3 empirical headline, not a fully-validated rule
catalog.
