# AgentTest — Lightning Presentation Talking Points

> This document expands the project against the four-piece structure
> required by [`docs/ASSIGNMENT.md`](ASSIGNMENT.md) § Lightning
> Presentation, as a rehearsal script for the final presentation.
> Constraints (verbatim from ASSIGNMENT):
>
> - **2–3 minutes** total
> - **Slides required**
> - **No live demo needed** — a screenshot, short clip, or sample
>   output is sufficient for the artifact snapshot
> - Must cover four pieces: **Context, user, and problem** →
>   **Solution and design** → **Evaluation and results** →
>   **Artifact snapshot**

Authoritative sources:
- Design rationale: [`docs/project_plan.md`](project_plan.md)
- Full N=3 results: [`experiments/realworld-results.md`](../experiments/realworld-results.md)
- Skill entry point: [`claude-skill/agenttest/SKILL.md`](../claude-skill/agenttest/SKILL.md)

---

## 1. Context, user, and problem

### 1.1 Who is the user

A **Java developer** building an AI-agent product on the
**Spring AI / LangChain4j / MCP** stack. Primary persona is an
individual engineer or a small team that owns the agent codebase and
writes their own JUnit tests.

### 1.2 What workflow we are improving

Writing unit tests for newly written or modified agent code. The
painful subset is **agent-specific** tests — invariants a general
Java test generator does not understand:

- **Prompt injection** (LLM01 / ASI01) — user input or prior LLM
  responses cycled into the next prompt with no sanitize
- **Excessive agency** (LLM06 / ASI02 / ASI04 / ASI05 / ASI08) —
  unbounded LLM-controlled iteration, tool description ↔
  implementation drift, MCP tool-definition poisoning, cascading
  sub-agent failures
- **Sensitive-data disclosure** (LLM02) — sensitive data leaking
  into prompts or logs

### 1.3 Why this problem matters

Agent code is exposed to a class of bugs that traditional Java code
is not. These bugs are **disproportionately invisible** to:

1. **Traditional test suites** — they test functional correctness,
   not adversarial robustness or agent-pattern conformance
2. **Vanilla LLM test generators** — our N=3 evaluation shows that
   on three real `spring-ai-examples` files, vanilla Claude Code
   produces tests that catch **zero** OWASP risks; everything it
   writes is behavior-match

Closing this gap saves the developer hours per week of writing these
tests by hand and lowers the probability of an agent-class bug
shipping unnoticed.

### 1.4 Where this fits in prior art

| Category | Representative | What it does | What it doesn't |
|---|---|---|---|
| General LLM test generators | TestSpark, ChatUniTest, Diffblue, Qodo Cover | Optimize line coverage + mutation score on generic code | Benchmarks (HumanEval-Java, Defects4J) contain **no agent code** and no OWASP-class bugs |
| OWASP audit skills | `agamm/claude-code-owasp`, `AgriciDaniel/claude-cybersecurity` | Cross-language OWASP best-practice review / multi-agent security review | **Audit, not test generation** |
| Static analyzers | SpotBugs, SonarQube, SemGrep | Pattern detection | Cannot emit JUnit tests; rule libraries don't cover OWASP LLM categories |

The intersection — *source-level + OWASP-aligned + Java-agent-specific
+ JUnit-emitting* — is empty in the prior art. That is the niche
AgentTest fills.

### 1.5 Why GenAI is the right tool for this task

ASSIGNMENT explicitly asks every project to show "why GenAI is useful
for this task." Three concrete reasons it can't be done with static
analysis or templates:

1. **OWASP risk descriptions are English semantic context.** Mapping
   *"Prompt Injection occurs when user prompts alter the LLM's
   behavior or output in unintended ways…"* to a specific Spring AI
   prompt-template assembly call site requires language understanding
   — not keyword matching, not AST pattern rules.
2. **Generating JUnit 5 + Mockito source that tests adversarial input
   is unambiguously generation.** The assertion captures an invariant
   the LLM *infers* from the OWASP risk description applied to the
   *specific* Java code in front of it.
3. **Avoiding the tautological-assertion failure mode requires
   contract reasoning.** A test that asserts "the code does what the
   code does" doesn't catch bugs (the bug IS the current behavior).
   Separating *what the function should do under attack* from *what
   the implementation currently does* is exactly the kind of judgment
   GenAI is suited to.

Static analyzers (SpotBugs, SemGrep) flag patterns but can't emit
JUnit. Template generators produce coverage boilerplate, not
risk-targeted adversarial tests. General LLM test generators optimize
line coverage on benchmarks (HumanEval-Java, Defects4J) that contain
no agent code and no OWASP-class bugs.

---

## 2. Solution and design

### 2.1 What we built (one sentence)

A Claude Code skill installed at `~/.claude/skills/agenttest/`. When
the user types `/agenttest <file>` in any Maven Java project, the
skill reads the file → classifies the agent pattern → loads the
matching OWASP risk + Java rules → plans Given-When-Then test cases
→ asks for confirmation → generates a JUnit 5 + Mockito test class
→ runs `mvn test-compile` to verify → prints the source for the
user to **review before writing to disk**.

**The LLM that does the work is the user's existing Claude Code
session** — there is no separate engine, no `ANTHROPIC_API_KEY`, no
second LLM service. The skill is markdown rules loaded into a session
that is already there. The value-add is **OWASP grounding +
agent-pattern recognition + invariant-test discipline**, not a fancier
LLM call.

### 2.2 Architecture (12 modular markdown files)

```
SKILL.md (7-step orchestrator, ~150 lines)
  ├── rules/general/          — cross-language test discipline
  │   ├── attack-payload-assertions.md
  │   └── existing-test-awareness.md
  ├── rules/owasp/            — LLM01 / LLM02 / LLM06 invariants + payloads
  │   ├── llm01-prompt-injection.md
  │   ├── llm02-sensitive-disclosure.md
  │   └── llm06-excessive-agency.md
  ├── rules/patterns/         — agent-pattern classification
  │   ├── chain-workflow.md
  │   ├── iterative-agent.md
  │   ├── tool-handler.md
  │   └── log-handler.md
  ├── rules/java/             — JUnit 5 + Mockito + AssertJ + ChatClient mocking
  │   ├── junit-template.md
  │   └── chatclient-mocking.md
  └── rules/post-generation/  — mvn verification
      └── verify.md
```

**Key engineering choice**: rules are **loaded on-demand** — Step 1
pattern classification decides which OWASP + pattern files to load.
Nothing is loaded eagerly. `SKILL.md` itself stays lean.

### 2.3 The 7-step workflow

| Step | Action | Refusal license |
|---|---|---|
| 1 | Read target + classify agent pattern (chain workflow / iterative-agent / tool-handler / log-handler) | No match → refuse "no agent pattern detected" |
| 2 | Load matching OWASP risk rule(s) + general rules | — |
| 3 | Output a Given-When-Then test-case table (**plan before code**) | Cannot formulate an OWASP-relevant test → refuse |
| 4 | `AskUserQuestion` to confirm | User declines → stop |
| 5 | Read Java rules → generate `<TargetClass>AgentGenTest` | Only reference symbols visible in the target source — never invent inner classes |
| 6 | `mvn test-compile` (max 5 retries) + `mvn test -Dtest=…` | Retry budget exhausted → deliver source **with warning** |
| 7 | Print test source + case table + verification report | **Never** write to `src/test/java/` without explicit user confirmation |

### 2.4 Key GenAI design choices

1. **Skill-native, not engine wrapper.** Mid-S4 review pivoted the
   architecture from a FastAPI engine pipeline to a markdown rules
   tree. Three reasons:
   - Matches Claude Code skill design philosophy (prompt-time
     augmentation)
   - No second API key for the grader (the user's existing Claude
     Code subscription covers all LLM calls)
   - Runs against the user's **real** Spring AI Maven classpath, not
     stub jars

2. **OWASP-anchored risk taxonomy.** No invented risk categories.
   Every emitted test method's javadoc cites a specific OWASP risk
   ID (LLM01, LLM06, etc.) plus the Agentic 2026 ASI mapping
   (ASI01–ASI08). **6 of 10** Agentic 2026 ASI risks are covered by
   Java unit tests (ASI03/06 multi-tenant + memory poisoning out of
   scope; ASI09/10 are not unit-testable).

3. **Attack-payload assertions as the technical contribution.**
   Tests inject canonical OWASP payloads (`}}`, `<|im_start|>`,
   `[INST]`, `Ignore previous`, …) and assert that the payload chars
   do **not** survive into the captured LLM input / log output / tool
   side-effect. Sharper than abstract "invariant tests" framing, and
   doesn't overlap with general Java testing skills.

4. **Human stays in the loop.** SKILL.md Step 7 explicitly says:
   > "do NOT write to `src/test/java/` without explicit user confirmation"

   Every generated test is **advisory**; if no agent pattern matches,
   the skill **refuses** rather than fabricating. This satisfies
   ASSIGNMENT's "where a human should stay involved" requirement
   AND engineering common sense (an LLM-written test that asserts
   the wrong invariant is worse than no test — it locks bad behavior in).

5. **Locked baseline = vanilla Claude Code session.** Same Claude
   Code build, identical tool access (Read, Grep, Bash), only the
   skill grounding differs. **No tool asymmetry** — the comparison
   is cleanly "framing vs no framing", not "more tools vs fewer
   tools".

### 2.5 Course concepts covered

ASSIGNMENT requires at least two; the design lands on three naturally:

- **Multi-step orchestration (Week 5)** — 7-step SKILL.md workflow
  with refusal license at multiple steps; each step has a typed
  expectation
- **Structured outputs (Weeks 2–3)** — Step 7 prints test source +
  Given-When-Then case table + verification report (V_buggy/V_clean
  PASS/FAIL) — a structured view, not a wall of text
- **Governance / deployment controls (Week 6)** — explicit
  human-in-the-loop, generated tests never auto-merged

*Retrieval-Augmented Generation (Week 4) is intentionally not used.*
The pre-pivot engine had RAG over OWASP catalog + agent-pattern
library; the skill replaces this with 12 on-demand markdown files —
simpler, no embedding service, no second key.

---

## 3. Evaluation and results

### 3.1 What we compared against

**Locked baseline = vanilla Claude Code session + locked prompt.**
Captured 2026-05-06 with Claude Code v2.x; identical across all three
samples:

> 帮我给 ChainWorkflow.java 写一个测试
> *(English: "Help me write a test for ChainWorkflow.java")*

Same Claude Code build, skill installed but `/agenttest` **not
invoked**. This is **fair** because it is exactly what a developer
using Claude Code alone would produce. All three vanilla outputs
are committed verbatim under
[`experiments/{chainworkflow,orchestratorworkers,evaluatoroptimizer}/test_vanilla.java`](../experiments/).

### 3.2 Test set — 3 real OSS files

From [`spring-projects/spring-ai-examples`](https://github.com/spring-projects/spring-ai-examples)
@ commit `2a6088db3d18d5fa6fc208b12adf1172d22f77fd`:

| Sample | Pattern | Real upstream OWASP risk |
|---|---|---|
| `ChainWorkflow.java` | chain workflow | Line 121 `String.format("{%s}\n {%s}", prompt, response)` cycles user input + LLM response into the next step's prompt with no sanitize (**LLM01 direct + indirect**) |
| `OrchestratorWorkers.java` | iterative-agent (fan-out) | Line 189 streams over an LLM-controlled `tasks` list with **no upper bound** (LLM06 / ASI08); inputs flow into prompts unsanitized (LLM01 + ASI07) |
| `EvaluatorOptimizer.java` | iterative-agent (recursion) | Lines 212–235 are an **unbounded recursive** loop (only `evaluation == PASS` exits → LLM06 / ASI08); evaluator `feedback` flows into next-iteration `context` unsanitized (LLM01 indirect / ASI04) |

**Real OSS files with real bugs** — no synthetic injection. The
"self-validation problem" that plagued the pre-pivot engine era
(writing a bug then testing whether we catch it) is structurally
absent: **we did not write the bug**.

### 3.3 The rubric

```
V_buggy = upstream code as-is (real OWASP risk present)
V_clean = hand-fixed (sanitize() helper + bounded loop where applicable)

A = skill mode output (/agenttest invocation)
B = vanilla mode output (locked baseline prompt)

Drop A or B into V_buggy → mvn test → expected FAIL  (catch / recall)
Drop A or B into V_clean → mvn test → expected PASS  (precision)
```

**Catch criterion** (mechanical, **no LLM-as-judge**):
- `mvn test` exit ≠ 0
- AND failure messages match regex
  `(?i)(sanitize|injection|template.?breakout|system\s*:|prompt.?inject)`

**Precision criterion**: every test in the set passes on V_clean.

### 3.4 Results — N=3 final headline

| Sample | Pattern | skill catches | skill precision | vanilla catches | vanilla precision |
|---|---|---|---|---|---|
| ChainWorkflow | chain workflow | **4 / 4** ✓ † | 5 / 5 ✓ | 0 / 5 ✗ | 5 / 5 ✓ |
| OrchestratorWorkers | iterative-agent (fan-out) | **4 / 4** ✓ | 4 / 4 ✓ | 0 / 7 ✗ | 7 / 7 ✓ |
| EvaluatorOptimizer | iterative-agent (recursion) | **4 / 4** ✓ | 4 / 4 ✓ | 0 / 7 ✗ | 7 / 7 ✓ |
| **TOTAL** | 3 patterns | **12 catches** | **13 / 13 PASS** | **0 catches** | **19 / 19 PASS** |

† ChainWorkflow's skill output is 4 attack-payload tests + 1 sanity
test (always-PASS by design); the catch denominator counts the
attack-payload tests only. Precision counts all 5.

**12-0 catch differential, both sides have intact precision** —
neither false-positives on V_clean. The delta is **framing**, not
technical capability: vanilla writes behavior-match tests (asserts
"what the code currently does"); skill writes invariant tests
anchored to OWASP attack payloads (asserts "what should hold
regardless of current code state").

### 3.5 Cross-cutting findings (abridged from [`experiments/realworld-results.md`](../experiments/realworld-results.md))

1. **Vanilla has the technical chops, lacks the framing.** All three
   vanilla outputs used the correct Spring AI 1.0 fluent-API mocks
   (`ChatClientRequestSpec`, `CallResponseSpec`, `PromptUserSpec`),
   correct `ArgumentCaptor.getAllValues()`, correct
   `verify(times(N))`. The difference is **purely** behavior-match
   vs invariant — **not knowledge, framing**.
2. **Indirect-injection coverage is consistent across patterns.** The
   skill caught the indirect-injection surface specific to each
   pattern (response cycling / task-field flow / feedback context) —
   same OWASP risk, three different surface shapes.
3. **V_clean scope must match catch scope (methodology lesson).** Our
   first V_clean fixed only the headline LLM06 risk, leaving LLM01
   tests at precision 0/4. V_clean v2 added comprehensive `sanitize()`
   and reached 4/4. The lesson: V_clean must be a comprehensive fix
   for *every* OWASP risk the skill flags, not just the headline one
   — a real engineer reading skill output would do the same.
4. **Skill rule throw-vs-truncate consistency gap (future work).**
   `iterative-agent.md` Invariant 1 (bounded recursion) explicitly
   accepts a throwing fix via `assertThatThrownBy`; Invariant 2
   (LLM fan-out cap) uses bare `verify(atMost(...))` with no try/catch
   — which means a throwing V_clean errors out the test. We worked
   around this by truncating in OrchestratorWorkers V_clean. Both
   throw and truncate are defensible; the rule should accept either.

### 3.6 Limitations (acknowledged on a slide)

- **N=3 is existence proof, not benchmark.** Universal claims
  ("skill > vanilla on all Java AI code") would need N=15+ across
  more patterns + frameworks. Out of scope for a Week-7 deliverable.
- **Self-selected samples.** We chose iterative-agent variants
  precisely because the skill has unvalidated rules for them.
  `tool-handler`, `log-handler`, MCP server patterns are **not**
  end-to-end validated in N=3 — they are documented rules without
  an empirical run.
- **V_clean scope must match catch scope** (methodology lesson). The
  first V_clean only fixed LLM06, leaving LLM01 tests at precision
  = 0/4. V_clean v2 added comprehensive `sanitize()` and reached
  4/4. This is a V_clean defect, not a skill defect.
- **Maven only** — shells out to `mvn test-compile` / `mvn test`.
  Gradle / Bazel not supported.
- **Java only** — no Kotlin / Scala.
- **Spring AI 1.0 fluent API only** — `chatclient-mocking.md`
  encodes the `ChatClient.prompt().user(...).call()` shape.
  LangChain4j and raw MCP clients have different APIs.

### 3.7 What we explicitly did NOT do (and why)

Stated up front so a grader doesn't read these as missing:

- **No live demo.** ASSIGNMENT explicitly says one is not required;
  using a sample-output snapshot is lower-risk in a 2–3 min window.
- **No N=15+ benchmark.** N=3 is sized as an existence proof for a
  Week-7 deliverable; a benchmark-grade evaluation is future work.
- **No tool-handler / log-handler end-to-end validation.** Rules for
  these patterns exist in the skill but are not exercised in N=3 —
  `spring-ai-examples` had no clean log-handler target at the time
  of the eval.
- **No RAG.** The pre-pivot engine had it. Skill-native uses 12
  on-demand markdown files instead — simpler, no embedding service,
  no second key. Week-4 RAG concept intentionally not used.
- **No model-as-judge for the catch criterion.** Catch is mechanical:
  `mvn test` exit + grep regex on failure messages. No LLM grades
  any test. Deliberate methodology choice to avoid circular evaluation.
- **No engine / FastAPI server in the deliverable.** The S4 pivot
  deleted the engine (commit `99df6e0`). Recoverable from git history
  if archeology is needed; not part of the shipped artifact.

---

## 4. Artifact snapshot

ASSIGNMENT explicitly says **no live demo required** — a screenshot,
short clip, or sample output is enough. Our strongest artifact is a
**side-by-side code comparison**: same `ChainWorkflow.java`, same
`ArgumentCaptor.getAllValues()` recipe, **opposite framing**.

### 4.1 What `/agenttest` produces (chain pattern, LLM01 direct)

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
                .as("LLM01: rendered prompt must not leak template-breakout payload")
                .doesNotContain("}}")
                .doesNotContain("Ignore previous")
                .doesNotContain("system:");
    }
}
```

### 4.2 What `/agenttest` produces (iterative-agent, LLM06 / ASI08 fan-out)

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

    // Then: total prompt() calls must be capped (1 orchestrator + at most ~20 workers)
    verify(chatClient, atMost(REASONABLE_WORKER_CAP + 1)).prompt();
}
```

### 4.3 What vanilla Claude produces (**same** ChainWorkflow.java)

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

### 4.4 The key insight — say this exact line on stage

> Same `ArgumentCaptor.getAllValues()` recipe both sides; opposite
> framing. Vanilla **locks the test to the current literal format
> string** — which means it passes on the buggy upstream code AND on
> the fixed code: **it doesn't catch the LLM01 vulnerability either
> way**. Skill asserts that **no canonical OWASP attack payload
> survives in any captured prompt** — it fails on the buggy code,
> passes on the fix.

### 4.5 Full artifacts (one-line reference on closing slide)

- [`experiments/chainworkflow/`](../experiments/chainworkflow/) —
  test_skill.java, test_vanilla.java, V_clean baseline, smoke-result.md
- [`experiments/orchestratorworkers/`](../experiments/orchestratorworkers/)
- [`experiments/evaluatoroptimizer/`](../experiments/evaluatoroptimizer/)
- [`experiments/realworld-results.md`](../experiments/realworld-results.md) —
  full N=3 data + methodology + 4 cross-cutting findings

---

## 5. Slide outline (sized for 2–3 minutes)

| # | Slide | Time | Content | Speaker notes (spoken voice) |
|---|---|---|---|---|
| 1 | **Title** | 5s | "AgentTest — JUnit tests for AI agent code, OWASP-grounded" | "AgentTest is a Claude Code skill that generates JUnit tests for Java AI agent code." |
| 2 | **Context** | 30–40s | User / workflow / pain point (one diagram: Java agent code → traditional tests miss OWASP-class bugs) | "The user is a Spring AI developer. The pain is agent-specific test invariants — prompt injection, excessive agency, sensitive-data leakage — that traditional test suites don't see, and that general LLM test generators don't see either. Our evaluation shows vanilla Claude Code catches **zero** OWASP risks across three real files." |
| 3 | **Solution** | 30–40s | 7-step skill orchestrator + 12 markdown rules (architecture diagram) + the three design choices | "We built a Claude Code skill — `/agenttest <file>` triggers a 7-step flow that loads 12 modular markdown rules on-demand. Three key design choices: skill-native, not an engine wrapper; OWASP-anchored risk taxonomy; assertions on attack payloads instead of behavior matching." |
| 4 | **Evaluation** | 40–50s | Methodology (V_buggy/V_clean + mechanical catch criterion) + the 12-0 results table | "The baseline is the same Claude Code session — only the skill grounding differs. Three real OSS files. V_buggy run expects FAIL (that's catch); V_clean run expects PASS (that's precision). The result is **12 catches vs 0**, with intact precision on both sides. The delta is **framing, not technical capability**." |
| 5 | **Artifact** | 20–30s | Side-by-side: skill test vs vanilla test on the same file | "Two tests for the same `ChainWorkflow.java` — same `ArgumentCaptor` recipe, opposite framing. Vanilla locks the test to the current format string; skill asserts that no OWASP payload survives." |
| 6 | **Limits + Wrap** | 10–15s | N=3 is existence proof / Maven only / Spring AI 1.0 only / human-in-the-loop | "N=3 is an existence proof, not a benchmark. Maven, Java, Spring AI 1.0 only. Every generated test is advisory — never auto-merged." |

**Estimated total**: ≈ 2 min 30 s (within the 2–3 min window).

---

## 6. Key numbers cheat-sheet (memorize before stage)

| Number | Meaning |
|---|---|
| **12 / 0** | skill catches vs vanilla catches (the headline) |
| **13/13 + 19/19** | both sides at full precision (no false positive on V_clean) |
| **N=3** | three real OSS files, three different agent patterns |
| **commit `2a6088d`** | the pinned `spring-ai-examples` commit |
| **7 steps** | SKILL.md orchestrator size |
| **12** | total modular markdown rule files |
| **$0** | grader's marginal cost (covered by Claude Code subscription, no second API key) |

---

## 7. Rehearsal checklist

- [ ] Can deliver all four pieces in **under 3 minutes** (rehearse
      twice against a timer)
- [ ] The 12-0 table is on a slide (visual anchor for the headline)
- [ ] The skill-vs-vanilla side-by-side code is on a slide
      (artifact snapshot)
- [ ] Speaker notes include the **"framing not knowledge"** line
- [ ] Speaker notes acknowledge **N=3 limit** (don't pretend it's
      a benchmark)
- [ ] Speaker notes mention **human-in-the-loop / advisory**
      (ASSIGNMENT requirement)
- [ ] **No** live demo scheduled (ASSIGNMENT says not needed; lower
      risk)
- [ ] Closing slide has the repo URL: `github.com/c1375/AgentTest`

---

## 8. Likely Q&A (have one-line answers ready)

| Question | One-line answer |
|---|---|
| Why is N=3 enough? | N=3 is an **existence proof** — that the framing differential exists across distinct agent patterns. A universal claim would need N=15+, but that's outside a Week-7 deliverable. |
| Why not just test whether vanilla "knows" OWASP? | That's exactly what the locked-prompt baseline measures — it's the natural output a developer using Claude Code alone would get. Vanilla doesn't *not know* OWASP; it defaults to behavior-match tests. |
| What if the skill itself asserts the wrong invariant? | That's why precision on V_clean is part of the rubric — tests must pass on V_clean. Both sides held precision in N=3. **And final review is always human.** |
| Why pivot from engine to skill? | Three reasons: matches Claude Code skill design philosophy; no second API key for the grader; runs against the user's **real** Spring AI Maven classpath instead of stub jars. |
| Did you copy `clear-solutions/unit-tests-skills`? | We adopted a similar multi-file `rules/` **structure** — but all rule **content** is written fresh (clear-solutions has no LICENSE file, so we did not fork its prose). |
| Why no RAG? | The pre-pivot engine had it. The skill replaces it with 12 on-demand markdown files — simpler, no embedding service, no second key. The Week-4 RAG concept was intentionally not used. |

---

## 9. Source documents

| Information | File |
|---|---|
| Course requirements (binding) | [`docs/ASSIGNMENT.md`](ASSIGNMENT.md) |
| Design rationale + full sprint history | [`docs/project_plan.md`](project_plan.md) / [`.zh.md`](project_plan.zh.md) |
| User-facing surface (README) | [`README.md`](../README.md) |
| Skill entry point | [`claude-skill/agenttest/SKILL.md`](../claude-skill/agenttest/SKILL.md) |
| Full N=3 results | [`experiments/realworld-results.md`](../experiments/realworld-results.md) |
| Per-sample raw artifacts | [`experiments/{chainworkflow,orchestratorworkers,evaluatoroptimizer}/`](../experiments/) |
| Chinese version of this document | [`docs/presentation.zh.md`](presentation.zh.md) |
