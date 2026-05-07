# AgentTest

A Claude Code skill that generates JUnit 5 tests for Java AI agent code
(Spring AI / LangChain4j / MCP), grounded in canonical OWASP LLM Top 10
attack payloads. Final project for a Generative AI course.

> **Generated tests are advisory.** A human must review every test
> before it lands in `src/test/java`. AgentTest does not auto-merge.

## TL;DR

Three real files in [`spring-projects/spring-ai-examples`](https://github.com/spring-projects/spring-ai-examples)
@ commit `2a6088d`, vanilla Claude Code (locked baseline prompt) vs
skill mode (`/agenttest <file>`):

| Sample | Pattern | skill catches | skill precision | vanilla catches | vanilla precision |
|---|---|---|---|---|---|
| `ChainWorkflow.java` | chain workflow | **4 / 4** ✓ † | 5 / 5 ✓ | 0 / 5 ✗ | 5 / 5 ✓ |
| `OrchestratorWorkers.java` | iterative-agent (fan-out) | **4 / 4** ✓ | 4 / 4 ✓ | 0 / 7 ✗ | 7 / 7 ✓ |
| `EvaluatorOptimizer.java` | iterative-agent (recursion) | **4 / 4** ✓ | 4 / 4 ✓ | 0 / 7 ✗ | 7 / 7 ✓ |
| **TOTAL** | 3 patterns | **12 catches** | 13 / 13 PASS | **0 catches** | 19 / 19 PASS |

† ChainWorkflow's skill output is 4 attack-payload tests + 1 sanity
test (always-PASS); the catch denominator counts attack-payload tests
only. Precision counts all 5.

**12-0 catch differential, both modes have intact precision.** The
delta is **framing**, not technical capability — vanilla writes
behavior-match tests; skill writes invariant tests anchored to OWASP
attack payloads. N=3 is an existence proof across pattern variants,
not a benchmark. Full data:
[`experiments/realworld-results.md`](experiments/realworld-results.md).

## Context, user, and problem

**Who.** A Java developer building an AI-agent product on the Spring
AI / LangChain4j / MCP stack. The primary persona is an individual
engineer or a small team that owns an agent codebase and writes JUnit
tests for their own code.

**Workflow.** Writing unit tests for newly written or modified agent
code. The painful subset is *agent-specific* tests — invariants a
general Java test generator does not understand:

- **Prompt injection** in template assembly (LLM01)
- **Excessive agency** — tool description ↔ implementation drift,
  unbounded LLM-controlled iteration (LLM06 / ASI02 / ASI08)
- **Sensitive-data leakage** into prompts or logs (LLM02)

**Why it matters.** Agent code is disproportionately exposed to a
class of bugs that traditional Java code is not — prompt injection,
tool-contract drift, sensitive-data leakage, multi-tenant boundary
failures, retry / idempotency violations. These bugs are also
disproportionately *invisible* to traditional test suites (which test
functional correctness, not adversarial robustness or agent-pattern
conformance) AND to vanilla LLM test generators — our N=3 eval shows
vanilla Claude Code writes behavior-match tests on three real
spring-ai-examples files and catches **zero** of the OWASP risks
present. Closing that gap saves the developer hours per week of
writing these tests by hand and lowers the probability of an
agent-class bug shipping unnoticed.

**Where this fits in prior art.** General LLM test generators
(TestSpark, ChatUniTest, Diffblue, Qodo Cover) optimize line coverage
+ mutation score on generic code; their benchmarks (HumanEval-Java,
Defects4J) contain no agent code and no OWASP-class bugs. OWASP audit
skills (`agamm/claude-code-owasp`, `AgriciDaniel/claude-cybersecurity`)
do review, not test generation. The intersection — *source-level,
OWASP-aligned, Java-agent-specific, JUnit-emitting* — is where
AgentTest fits.

## Solution and design

**What we built.** A Claude Code skill installed at
`~/.claude/skills/agenttest/`. When the user types `/agenttest <file>`
in any Maven Java project, the skill (per
[`SKILL.md`](claude-skill/agenttest/SKILL.md)) reads the file,
classifies the agent pattern, loads matching OWASP risk + Java rule
files, plans Given-When-Then test cases, asks for confirmation,
generates a JUnit 5 + Mockito test class, runs `mvn test-compile`
to verify, and prints the source for the user to review before
writing to disk.

**Architecture** (12 modular markdown files, loaded on-demand by
Step 1 pattern classification):

```
SKILL.md (7-step orchestrator)
  ├── rules/general/         — cross-language test discipline
  ├── rules/owasp/           — LLM01 / LLM02 / LLM06 invariants + payloads
  ├── rules/patterns/        — chain-workflow / iterative-agent / tool-handler / log-handler
  ├── rules/java/            — JUnit 5 + Mockito + AssertJ + ChatClient mocking
  └── rules/post-generation/ — mvn test-compile + mvn test verification
```

The user's existing Claude Code session does the LLM work — there is
no separate engine, no `ANTHROPIC_API_KEY`, no second LLM service.

**Key design choices:**

- **Skill-native, not engine.** Sprint-4 mid-sprint review pivoted
  from a FastAPI engine pipeline to a markdown rules tree loaded
  into the user's Claude Code session. Three reasons: matches Claude
  Code skill design philosophy (prompt-time augmentation), no second
  API key for the grader, validates against the user's real Spring
  AI Maven classpath. Full pivot rationale:
  [`docs/plan/sprint-4.md`](docs/plan/sprint-4.md) § "Why pivot".
- **OWASP-anchored risk taxonomy.** No invented risk categories.
  Every emitted test method's javadoc cites a specific OWASP risk
  ID (LLM01, LLM06, etc.) plus the Agentic 2026 ASI mapping (ASI01
  through ASI08 where applicable). 6 of 10 ASI 2026 risks covered
  by Java unit tests; ASI03/06 deferred (multi-tenant + memory
  poisoning out of scope); ASI09/10 not unit-testable.
- **Attack-payload assertions** as the technical contribution.
  Tests inject canonical OWASP payloads (`}}`, `<|im_start|>`,
  `[INST]`, etc.) and assert the payload chars do NOT survive into
  the captured LLM input / log output / tool side-effect — sharper
  than "invariant tests" framing and doesn't overlap with general
  Java testing skills.
- **Human stays in the loop.** SKILL.md Step 7 explicitly says
  "do NOT write to `src/test/java/` without user confirmation".
  Every generated test is advisory; refusal-as-output when no
  agent pattern is detected (no fabrication).
- **Locked baseline = vanilla Claude Code session.** Same Claude
  Code build, identical tool access (Read, Grep, Bash), only the
  OWASP grounding differs. No tool asymmetry; the only manipulated
  variable is whether the skill's instructions inject framing.

## Setup and usage

### Install

```pwsh
git clone https://github.com/c1375/AgentTest.git
cd AgentTest
.\bin\install-skill.ps1
```

Windows-only install script. **macOS / Linux** (untested):

```sh
mkdir -p ~/.claude/skills && cp -r claude-skill/agenttest ~/.claude/skills/
```

The skill installs to `~/.claude/skills/agenttest/`. It is
`disable-model-invocation: true` — Claude won't auto-trigger it; you
type `/agenttest <file>` explicitly.

**No API key needed.** AgentTest is prompt-time augmentation that
runs inside your existing Claude Code session.

### Invoke

In any Claude Code project that is a Maven Java project with Spring
AI / LangChain4j / MCP code:

```
/agenttest src/main/java/com/example/MyAgent.java
```

The skill will:

1. Read the target + classify the agent pattern (chain workflow /
   iterative agent / tool handler / log handler)
2. Load the matching OWASP risk file(s) and Java test rules
3. Plan test cases (Given-When-Then table)
4. Ask you to confirm
5. Generate the JUnit 5 test class
6. Run `mvn test-compile` (up to 5 retries) + report per-test outcomes
7. Print the test source for you to review before writing to disk

If the file isn't a Java AI agent pattern, the skill **refuses**
rather than guessing.

## Evaluation and results

### Methodology

For each (sample, mode) where `mode ∈ {vanilla, skill}`:

```
V_buggy = upstream code as-is (real OWASP risk present)
V_clean = hand-fixed (sanitize() + bounded loop where applicable)

A = Claude Code session output WITH skill (/agenttest invocation)
B = Claude Code session output WITHOUT skill (locked baseline prompt)

Drop A or B into V_buggy → mvn test → expected FAIL  (catch / recall)
Drop A or B into V_clean → mvn test → expected PASS  (precision)
```

**Catch criterion**: a (test set, V_buggy) pair counts as "catch"
iff `mvn test` exits non-zero AND the failure messages match
`(?i)(sanitize|injection|template.?breakout|system\s*:|prompt.?inject)`.
All 12 skill catches in our eval matched the regex; no false
positives required removal.

**Precision criterion**: every test in the set passes on V_clean.

Both vanilla and skill paths run inside Claude Code in **separate
fresh sessions** — identical tool access (Read, Grep, Bash), only
the skill grounding differs.

### Test set: 3 real OSS files

| Sample | Real upstream OWASP risk |
|---|---|
| `ChainWorkflow.java` | Line 121 `String.format("{%s}\n {%s}", prompt, response)` cycles user input + LLM response into next step's prompt with no sanitize (LLM01 direct + indirect) |
| `OrchestratorWorkers.java` | Line 189 streams over LLM-controlled `tasks` list with no upper bound (LLM06 / ASI08); inputs flow into prompts unsanitized (LLM01 + ASI07) |
| `EvaluatorOptimizer.java` | Lines 212–235 unbounded recursive loop (only PASS exits — LLM06 / ASI08); evaluator `feedback` flows into next-iteration `context` unsanitized (LLM01 indirect / ASI04) |

Real OSS files with real bugs — no synthetic injection. The
"self-validation problem" that troubled the pre-pivot engine eval is
structurally absent: we do not write the bug.

### Results — N=3 final headline

See the table in [TL;DR](#tldr). 12-0 catch differential; both modes
have intact precision (no false positives on `V_clean`).

### Cross-cutting findings (abridged from results.md)

1. **vanilla has the technical chops, lacks the framing.** All three
   vanilla outputs used the correct Spring AI 1.0 fluent-API mocks,
   correct `ArgumentCaptor.getAllValues()`, correct invocation-count
   verifies. The difference is purely behavior-match vs invariant —
   not knowledge.
2. **Indirect-injection coverage is consistent.** The skill caught
   the indirect-injection surface specific to each pattern (response
   cycling, task-field flow, feedback context) — same OWASP risk,
   three different surface shapes.

## Artifact snapshot

**Locked baseline prompt** (vanilla mode, used verbatim across all
three samples in our eval):

> 帮我给 ChainWorkflow.java 写一个测试
> *(English: "Help me write a test for ChainWorkflow.java")*

### What `/agenttest` produces (chain pattern, LLM01 direct)

```java
@Test
void chain_userInputContainsTemplateBreakout_noStepLeaksPayload() {
    // Given
    ArgumentCaptor<String> promptCaptor = ArgumentCaptor.forClass(String.class);
    when(chatClient.prompt(promptCaptor.capture())).thenReturn(promptSpec);
    when(promptSpec.call()).thenReturn(responseSpec);
    when(responseSpec.content()).thenReturn("benign step output");

    // When
    target.chain(PAYLOAD_TEMPLATE_BREAKOUT);

    // Then
    List<String> capturedPrompts = promptCaptor.getAllValues();
    assertThat(capturedPrompts).isNotEmpty();
    for (String captured : capturedPrompts) {
        assertThat(captured)
                .as("LLM01: rendered prompt must not leak template-breakout / instruction-override payload")
                .doesNotContain("}}")
                .doesNotContain("Ignore previous")
                .doesNotContain("system:");
    }
}
```

### What `/agenttest` produces (iterative-agent pattern, LLM06 / ASI08 fan-out)

```java
@Test
void process_orchestratorReturns1000Tasks_workerCountIsCappedAtReasonableBound() {
    // Given: a runaway / malicious LLM emits 1000 subtasks
    List<Task> hugeTaskList = IntStream.range(0, 1000)
            .mapToObj(i -> new Task("type-" + i, "do thing " + i))
            .toList();
    when(callResponseSpec.entity(OrchestratorResponse.class))
            .thenReturn(new OrchestratorResponse("massive plan", hugeTaskList));
    when(callResponseSpec.content()).thenReturn("worker output");

    // When
    new OrchestratorWorkers(chatClient).process("trivial task");

    // Then: total prompt() calls must be capped (1 orchestrator + at most ~20 workers).
    verify(chatClient, atMost(REASONABLE_WORKER_CAP + 1)).prompt();
}
```

### What vanilla Claude produces (same `ChainWorkflow.java`, same fluent API)

```java
@Test
void chainFeedsPreviousResponseIntoNextStep() {
    when(callResponseSpec.content()).thenReturn("first-out", "second-out");
    String[] prompts = { "PROMPT_A", "PROMPT_B" };

    new ChainWorkflow(chatClient, prompts).chain("USER_INPUT");

    ArgumentCaptor<String> inputs = ArgumentCaptor.forClass(String.class);
    verify(chatClient, times(2)).prompt(inputs.capture());
    List<String> calls = inputs.getAllValues();

    assertThat(calls.get(0)).isEqualTo("{PROMPT_A}\n {USER_INPUT}");
    assertThat(calls.get(1)).isEqualTo("{PROMPT_B}\n {first-out}");
}
```

**Same `ArgumentCaptor.getAllValues()` recipe both sides; opposite
framing.** Vanilla locks the test to the current literal format
string; skill asserts that no canonical OWASP attack payload survives
in any captured prompt regardless of format. **Vanilla's test passes
on the buggy upstream code AND on the fixed code — it doesn't catch
the LLM01 vulnerability either way. Skill's test fails on the buggy
code, passes on the fix.**

Full artifacts:
[`experiments/chainworkflow/`](experiments/chainworkflow/) (test_skill.java, test_vanilla.java, V_clean baseline)
· [`experiments/orchestratorworkers/`](experiments/orchestratorworkers/)
· [`experiments/evaluatoroptimizer/`](experiments/evaluatoroptimizer/)

## Limitations + where this breaks down

- **N=3 is existence proof, not benchmark.** Universal claims ("skill
  > vanilla on all Java AI code") would need N=15+ across more
  patterns + frameworks. Out of scope for a Week-7 course deliverable.
- **Self-selected samples.** We chose iterative-agent variants
  (orchestrator-workers + evaluator-optimizer) for the stretch
  precisely because the skill has unvalidated rules for them.
  `tool-handler`, `log-handler`, MCP server patterns are not
  end-to-end validated in Phase 2.
- **V_clean scope must match catch scope.** First-pass V_clean for
  the two stretch samples fixed only the bounded-loop OWASP risk
  (`LLM06`), reasoning that this was the "stretch-specific" risk.
  The skill caught LLM01 prompt-injection variants in both samples
  too — so V_clean v1 had precision = 0/4. V_clean v2 (committed)
  added comprehensive `sanitize()` to inputs and LLM-emitted fields.
  Methodology lesson, not a skill defect: V_clean must fix every
  OWASP risk the skill identifies, not just the headline risk.
- **`iterative-agent.md` rule has a throw-vs-truncate consistency
  gap.** Invariant 1 (bounded recursion) explicitly accepts a
  throwing fix via `assertThatThrownBy`. Invariant 2 (LLM-determined
  fan-out cap) uses bare `verify(atMost(...))` with no try/catch —
  which means a throwing V_clean errors out the test. We worked
  around this by truncating in OrchestratorWorkers V_clean. Skill
  rule should accept either fix style; this is on the future-work
  list.
- **Maven-only.** Gradle / Bazel / non-Maven projects fall outside
  the skill's `mvn test-compile` + `mvn test` verification step.
- **Java-only.** No Kotlin, no Scala, no other JVM languages.
- **Spring AI 1.0 fluent API only.** `chatclient-mocking.md` rule
  encodes Spring AI's specific `ChatClient.prompt().user(...).call()`
  shape. LangChain4j and raw MCP clients have different APIs.
- **Demo clip is pending** — Phase 3 task 3 from
  [`docs/plan/sprint-4.md`](docs/plan/sprint-4.md). Will be linked
  here when recorded.

## What this is NOT

- **Not auto-merge.** Generated tests are advisory; you review
  before they land.
- **Not OWASP audit / review.** Audit skills exist already (see
  Related work). AgentTest fills the adjacent niche of *test
  generation* for AI agent code.
- **Not a wrapper around a separate LLM service.** No
  `ANTHROPIC_API_KEY`, no FastAPI server. The skill is markdown
  rules loaded into the same Claude Code session that does the work.

## Architecture journey

S1–S3 (Weeks 4–6) built a FastAPI engine pipeline (analyzer /
retrieval / generator / validator) on the assumption that "skill =
wrapper around external service". A mid-S4 review surfaced four
problems: self-validation (we wrote samples knowing what bug to
inject), classpath mismatch (validator stubs vs real Spring AI jars),
unclear product surface (a FastAPI server isn't user-facing), and
skill design philosophy mismatch (Claude Code skills are prompt-time
augmentation, not external LLM services). S4 pivoted to skill-native;
the engine was deleted in commit `99df6e0`. The journey is documented
in [`docs/plan/sprint-2.md`](docs/plan/sprint-2.md) →
[`sprint-3.md`](docs/plan/sprint-3.md) →
[`sprint-4.md`](docs/plan/sprint-4.md) (current SoT). Full pivot
rationale: `sprint-4.md` § "Why pivot".

## Related work (verified 2026-05-07)

- [`agamm/claude-code-owasp`](https://github.com/agamm/claude-code-owasp) —
  OWASP best-practice audit across many languages. Single ~21KB
  SKILL.md + companion OWASP report. **Audit, not test generation.**
- [`AgriciDaniel/claude-cybersecurity`](https://github.com/AgriciDaniel/claude-cybersecurity) —
  comprehensive cybersec code review with 8 specialist agents.
  **Audit, not test generation.**
- [`clear-solutions/unit-tests-skills`](https://github.com/clear-solutions/unit-tests-skills) —
  general Java JUnit test generation skill. Not AI-agent-specific;
  no OWASP grounding. We use a similar multi-file `rules/` tree but
  all rule content in AgentTest is written fresh (clear-solutions
  has no LICENSE file at time of writing — confirmed 2026-05-07).

AgentTest fills the adjacent niche: **JUnit test generation, Java
AI agent code, OWASP attack-payload assertions.** No novelty claim
on OWASP framing itself.

## Reproducibility

| Component | Pin |
|---|---|
| `spring-ai-examples` | commit `2a6088db3d18d5fa6fc208b12adf1172d22f77fd` |
| Java | OpenJDK 17+ on PATH |
| Maven | bundled `./mvnw` (3.9.x) |
| Claude Code | `2.x` (locked baseline prompt captured 2026-05-06) |

To reproduce a single sample's run, see
[`experiments/realworld-results.md`](experiments/realworld-results.md)
§ "Reproducibility" — a 5-step PowerShell snippet that drops the
test, runs `mvn test` against V_buggy and V_clean, and restores
upstream.

## Course context

Final project for a Generative AI course, **Week 7 deliverable**.

- [`docs/ASSIGNMENT.md`](docs/ASSIGNMENT.md) — course requirements (binding, verbatim from Canvas)
- [`docs/project_plan.md`](docs/project_plan.md) /
  [`docs/project_plan.zh.md`](docs/project_plan.zh.md) — design rationale (English / Chinese)
- [`docs/plan/sprint-{2,3,4}.md`](docs/plan/) — sprint history (S2/S3 archive the engine era; S4 is current)
- [`experiments/realworld-results.md`](experiments/realworld-results.md) — full N=3 data + methodology + findings
- [`experiments/{chainworkflow,orchestratorworkers,evaluatoroptimizer}/`](experiments/) — raw artifacts

## License

Apache License 2.0 — see [`LICENSE`](LICENSE).
