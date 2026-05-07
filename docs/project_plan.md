# AgentTest — Project Plan

> **S4 rewrite (2026-05-07)**: this document was rewritten in Sprint 4
> after the engine→skill pivot. The pre-pivot revision (FastAPI engine
> + analyzer/retriever/generator/validator pipeline + synthetic
> injection eval) is preserved in git history before commit `99df6e0`.
> § 8 archives the architecture journey. When this document and
> [`docs/ASSIGNMENT.md`](ASSIGNMENT.md) disagree, ASSIGNMENT wins.

## 1. Project title

**AgentTest** — a Claude Code skill that generates JUnit 5 tests for
Java AI agent code (Spring AI / LangChain4j / MCP), grounded in
canonical OWASP LLM Top 10 attack payloads.

The skill targets three classes of OWASP / Agentic-2026 risks the
upstream Spring AI / LangChain4j / MCP Java samples actually exhibit:

1. **LLM01 / ASI01** — direct prompt injection (template-breakout
   chars, conversation-turn markers, instruction-shape phrases) AND
   indirect injection via response cycling, tool output, evaluator
   feedback.
2. **LLM06 / ASI02 / ASI04 / ASI05 / ASI08** — excessive agency
   (unbounded LLM-controlled iteration, tool description ↔
   implementation drift, MCP tool-definition poisoning, cascading
   sub-agent failures).
3. **LLM02** — sensitive-data disclosure into prompts or logs.
   *(Deferred from N=3 eval — `spring-ai-examples` has no clean
   log-handler target.)*

OWASP is the **evaluation ground truth**: the catch criterion is
mechanical (`mvn test` exit + grep regex match on assertion messages),
no model-as-judge. The skill's coverage of "agent-pattern correctness"
and "reliability" classes from earlier framings rides on the same
rules tree but is not part of the headline metric.

## 2. Target user, workflow, and business value

**Who.** A Java developer building an AI-agent product on the Spring
AI / LangChain4j / MCP stack. The primary persona is an individual
engineer or a small team that owns a multi-tenant agent codebase and
writes JUnit tests for their own code. The design was originally
anchored on a real Spring Boot multi-tenant agent codebase the author
maintains; that codebase **never enters the deliverable, the grader
never sees it, and it never enters the eval set**. AgentTest is
evaluated on three real OSS files in `spring-ai-examples` (§ 5).

**Recurring task.** Writing unit tests for newly written or modified
agent code. The painful subset is *agent-specific* tests — invariants
a general Java test generator does not understand:

- **Safety** (OWASP-anchored): prompt-injection vectors in template
  assembly, sensitive-data leakage into prompts or logs, multi-tenant
  boundary violations, tool-description / implementation drift that
  amounts to excessive agency.
- **Agent-pattern correctness**: tool schema vs. implementation
  conformance, prompt-template stability across refactors, RAG-context
  invariants (only retrieved context reaches the model).
- **Reliability**: retry / circuit-breaker misconfiguration,
  idempotency under transient failure.

The safety bullet aligns with OWASP Top 10 for LLM Applications, OWASP
LLMSVS, and OWASP Top 10 for Agentic AI 2026 — the subset used for
**objective evaluation** (§ 5) because real OSS code already exhibits
these risks (no synthetic injection needed). General-purpose AI test
generators (TestSpark, ChatUniTest, Diffblue, etc.) optimize for line
coverage and mutation score on generic code; they have no agent
taxonomy and no Spring AI / LangChain4j / MCP knowledge, so they
consistently miss this class of bug.

**Where the workflow begins and ends.** The workflow begins when the
developer types `/agenttest <java-file>` in Claude Code on a Java
class implementing agent logic (`ChainWorkflow.java`,
`OrchestratorWorkers.java`, `MathTools.java`, etc.). It ends when the
developer has reviewed a generated JUnit 5 test class and either
accepted it into `src/test/java/...` or rejected it. **Generated
tests are advisory only — a human must review every test before it
lands**, both because LLM-written tests can lock the wrong invariant
(see § 5 cross-cutting findings) and because the course assignment's
"where a human should stay involved" requirement makes this control
explicit.

**Why better performance on this workflow matters.** Agent code is
disproportionately exposed to a class of bugs that traditional Java
code is not — prompt injection, tool-contract drift, sensitive-data
leakage, multi-tenant boundary failures, retry / idempotency
violations under transient failure. These bugs are also
disproportionately *invisible* to traditional test suites (which test
functional correctness, not adversarial robustness or agent-pattern
conformance). Closing the gap between "what general AI test
generators write" and "what an agent codebase actually needs to test"
saves the developer hours per week of writing these tests by hand and
lowers the probability of an agent-class bug shipping unnoticed.

## 3. Problem statement and GenAI fit

**The exact task.** Given a Java source file containing AI-agent
logic, emit a JUnit 5 test class. Each generated test method must:

1. Target a specific OWASP risk (e.g., LLM01, LLM06)
2. Reference the call site or method in the input class as the target
3. Produce JUnit 5 + Mockito + AssertJ assertions that **fail when
   the named risk is realized in the code, and pass when the code is
   clean** (V_buggy/V_clean methodology — § 5)
4. Compile against a standard Maven `spring-boot-starter-test`
   classpath

**Why GenAI.**

- OWASP risk descriptions are in English with implicit semantic
  context (e.g., LLM01: *"Prompt Injection occurs when user prompts
  alter the LLM's behavior or output in unintended ways…"*). Mapping
  that to a specific Spring AI prompt-template assembly call site
  requires language understanding — not keyword matching, not static
  analysis pattern rules.
- Generating valid JUnit 5 + Mockito source that **tests behavior
  under adversarial input** is unambiguously generation. The
  assertion must capture an invariant the LLM *infers* from the OWASP
  risk description applied to the *specific* Java code.
- Avoiding the *tautological assertion* failure mode (LLM writes a
  test that asserts "the code does what the code does") requires
  reasoning about *contract* — what the function *should* do under
  attack — separately from *implementation*.

**Why simpler alternatives fall short.**

- **Static analyzers** (SpotBugs / SonarQube / SemGrep) flag patterns
  but cannot emit executable JUnit tests, and their rule libraries
  do not cover OWASP LLM categories.
- **Template-based test generators** produce coverage-driven
  boilerplate, not risk-targeted adversarial tests.
- **General LLM test generators** (TestSpark, ChatUniTest, Qodo
  Cover) optimize for line coverage and mutation score on generic
  code. Their evaluation benchmarks (HumanEval-Java, Defects4J)
  contain no agent code and no OWASP-class bugs. They write tests
  that pass on prompt-injection-vulnerable code because that code
  "works" functionally — see § 5 N=3 evidence: vanilla Claude
  produces this exact failure mode on all three samples.
- **Runtime LLM red-teaming tools** (Garak, Spikee, AutoRedTeamer)
  probe deployed systems; they do not generate unit tests against
  source code.

The intersection — *source-level, OWASP-aligned, Java-agent-specific,
JUnit-emitting* — is empty in the prior art.

**Why a Claude Code skill (skill-native) and not a separate engine.**
The S4 architecture pivot was the central design decision. Three
reasons the skill-native path beats the engine path:

1. **Skill design philosophy match.** Claude Code skills are
   prompt-time augmentation — markdown rules loaded into the user's
   existing session. An engine that calls Anthropic separately
   defies this convention and forces a second API key on the user.
2. **No second LLM call cost.** The user's Claude Code subscription
   already covers the LLM. A separate engine doubles the spend.
3. **Real-world classpath alignment.** An engine validating against
   stub Spring AI jars tests a world the user never lives in. The
   skill runs `mvn test` against the user's actual classpath.

The skill's value-add is **OWASP grounding + agent-pattern
recognition + invariant-test discipline**, packaged as 12 markdown
rule files loaded on-demand. Not a fancier LLM call.

## 4. System design and baseline

### Architecture

```
User in Claude Code:  /agenttest src/main/java/com/example/Foo.java
                              │
                              ▼
                      [SKILL.md, 7-step orchestrator]
                              │
       Step 1: Read target + classify agent pattern
              ├── chain workflow / prompt assembler  → load rules/patterns/chain-workflow.md
              ├── iterative agent (variable LLM loop) → load rules/patterns/iterative-agent.md
              ├── tool handler / MCP server          → load rules/patterns/tool-handler.md
              └── log handler                        → load rules/patterns/log-handler.md
              (refuse if none)
                              │
       Step 2: Load matching OWASP rule(s)
              ├── chain / iterative → rules/owasp/llm01-prompt-injection.md
              ├── iterative / tool   → rules/owasp/llm06-excessive-agency.md (5 sub-sections)
              └── log handler        → rules/owasp/llm02-sensitive-disclosure.md
                              │
       Step 3: Read general discipline rules
              ├── rules/general/attack-payload-assertions.md
              └── rules/general/existing-test-awareness.md
                              │
       Step 4: Plan test cases (Given/When/Then table)
                              │
       Step 5: Ask user to confirm via AskUserQuestion
                              │
       Step 6: Read Java rules → generate test class
              ├── rules/java/junit-template.md
              └── rules/java/chatclient-mocking.md (Spring AI fluent API)
                              │
       Step 7: Verify (rules/post-generation/verify.md)
              ├── mvn test-compile (max 5 retries)
              └── mvn test -Dtest=<TargetClass>AgentGenTest
                              │
                              ▼
              JUnit 5 source printed; user reviews before
              writing to src/test/java/ (advisory, never auto-merged)
```

12 modular markdown files total. SKILL.md is ~150 lines; rules are
~50–250 lines each, loaded on-demand based on Step 1 classification.

### Stages (skill workflow vs. engine workflow)

| Stage | Engine era (S1-S3, deleted) | Skill era (S4, current) |
|---|---|---|
| Pattern detection | Python AST analyzer (`javalang`) | Claude reads + classifies via Step 1 rules |
| Risk catalog | YAML (`engine/configs/owasp.yaml`) | Markdown (`rules/owasp/*.md`) |
| Generation | Sonnet 4.6 via Anthropic API | Claude Code session (user's subscription) |
| Compile gate | `javac` in-memory + JavaParser | `mvn test-compile` in user's project |
| Run gate | Custom runner with stub classpath | `mvn test` against real Maven classpath |
| Refusal | Structured JSON `refused: bool` | SKILL.md's "refuse if no agent pattern" |

### What the user sees and does

**Single surface: `/agenttest <java-file>` in Claude Code.** No
separate CLI, no FastAPI server, no API key. The skill runs inside
the user's existing Claude Code session.

The README walks the grader through the install (`bin\install-skill.ps1`),
invocation, and one end-to-end example with sample output.

### Course concepts represented

The assignment requires at least two; the design lands on three
naturally suited to skill-native architecture.

**1. Multi-step orchestration (Week 5).** Seven-step `SKILL.md`
workflow with explicit refusal license at multiple steps. Each step
has a typed expectation; the skill cannot proceed past Step 6 if
`mvn test-compile` fails after retries.

**2. Structured outputs (Weeks 2–3).** Step 7 prints the test source
with a Given-When-Then case table, an expected-OWASP-risk-ID column,
and the verification report (per-method PASS/FAIL on V_buggy and
V_clean). The user sees a structured view, not a wall of text.

**3. Governance and deployment controls (Week 6).** Explicit
human-in-the-loop framing — the skill does **not** auto-write to
`src/test/java/` without user confirmation. Every test is advisory.
See § 7 for the full controls list.

*Retrieval-Augmented Generation (Week 4) is intentionally not used.*
The pre-pivot engine had RAG over OWASP catalog + agent-pattern
library. The skill replaces this with ~12 markdown rule files loaded
on-demand based on Step 1 classification — simpler, no embedding
service, no second key. The pivot rationale is summarized in § 8 below.

### Baseline

**Baseline = vanilla Claude Code session with a locked prompt.** Same
Claude Code build, skill installed but `/agenttest` not invoked.
The user types one prompt verbatim:

> 帮我给 `<File>.java` 写一个测试
> *(English: "Help me write a test for `<File>.java`")*

This is *fair* because it is what a developer using Claude Code alone
would produce — same model, same fluent API access (Mockito, AssertJ,
Spring AI types), same Java tooling. Only the OWASP grounding /
attack-payload-assertion discipline differs. **No tool asymmetry.**

The locked prompt was captured 2026-05-06 with Claude Code v2.x.
Three vanilla outputs are committed verbatim under
[`experiments/{chainworkflow,orchestratorworkers,evaluatoroptimizer}/test_vanilla.java`](../experiments/).

## 5. Evaluation plan and results

### Methodology

For each (sample, mode) where `mode ∈ {vanilla, skill}`:

```
V_buggy  = upstream code as-is (real OWASP risk present)
V_clean  = hand-fixed (sanitize() helper + bounded loop where applicable)

A = Claude Code session output WITH skill (/agenttest invocation)
B = Claude Code session output WITHOUT skill (locked baseline prompt)

Drop A or B into V_buggy → mvn test → expected FAIL  (catch / recall)
Drop A or B into V_clean → mvn test → expected PASS  (precision)
```

**Catch criterion**: a (test set, V_buggy) pair counts as "catch" iff
`mvn test` exits non-zero AND the failure messages match
`(?i)(sanitize|injection|template.?breakout|system\s*:|prompt.?inject)`.
Manual spot-check is allowed to **drop** false catches but **not** add
new ones.

**Precision criterion**: every test in the set passes on V_clean.

### Test set composition

Three real Java files from
[`spring-projects/spring-ai-examples`](https://github.com/spring-projects/spring-ai-examples)
@ commit `2a6088db3d18d5fa6fc208b12adf1172d22f77fd`:

| Sample | Pattern | Real upstream OWASP risk |
|---|---|---|
| `agentic-patterns/chain-workflow/.../ChainWorkflow.java` | chain workflow | Line 121 `String.format("{%s}\n {%s}", prompt, response)` cycles user input + LLM response into next step's prompt with no sanitize (LLM01 direct + indirect) |
| `agentic-patterns/orchestrator-workers/.../OrchestratorWorkers.java` | iterative-agent (fan-out) | Line 189 streams over LLM-controlled `tasks` list with no upper bound (LLM06 / ASI08); `taskDescription` + `task.type/description` flow into prompts unsanitized (LLM01 + ASI07) |
| `agentic-patterns/evaluator-optimizer/.../EvaluatorOptimizer.java` | iterative-agent (recursion) | Lines 212–235 unbounded recursive loop (only exits on PASS — LLM06 / ASI08); evaluator `feedback` flows into next-iteration `context` unsanitized (LLM01 indirect / ASI04) |

These are real OSS files with real bugs — no synthetic injection
needed. The "self-validation problem" that troubled the pre-pivot
engine eval (§ 8) is structurally absent: we do not write the bug.

### Results (N=3 final headline)

| Sample | skill catches | skill precision | vanilla catches | vanilla precision |
|---|---|---|---|---|
| ChainWorkflow | **4 / 4** ✓ † | 5 / 5 ✓ | 0 / 5 ✗ | 5 / 5 ✓ |
| OrchestratorWorkers | **4 / 4** ✓ | 4 / 4 ✓ | 0 / 7 ✗ | 7 / 7 ✓ |
| EvaluatorOptimizer | **4 / 4** ✓ | 4 / 4 ✓ | 0 / 7 ✗ | 7 / 7 ✓ |
| **TOTAL** | **12 catches** | 13 / 13 PASS | **0 catches** | 19 / 19 PASS |

† ChainWorkflow's skill output has 4 attack-payload tests + 1 sanity
test (always-PASS by design); the catch denominator counts the
attack-payload tests only. Precision counts all 5.

**12-0 catch differential.** Both modes have intact precision —
neither false-positives on V_clean.

### Cross-cutting findings (full version: [`experiments/realworld-results.md`](../experiments/realworld-results.md))

**Finding 1 — Vanilla has the technical chops, lacks the framing.**
All three vanilla outputs used the correct Spring AI 1.0 fluent-API
mocks (`ChatClient.ChatClientRequestSpec`, `CallResponseSpec`,
`PromptUserSpec`), correct `ArgumentCaptor.getAllValues()`, correct
invocation-count `verify(times(N))` patterns. Every vanilla test was
*behavior-match* ("the code does X"), not *invariant* ("the code
SHOULD do Y regardless of current state"). The delta is purely
framing — same tool, opposite direction.

**Finding 2 — Indirect-injection coverage is consistent across
patterns.** All three skill outputs caught the indirect-injection
surface specific to each pattern:
- ChainWorkflow: LLM response → next step's prompt
- OrchestratorWorkers: orchestrator's `task` fields → worker prompts
- EvaluatorOptimizer: evaluator feedback → next-iteration context

The skill's `rules/owasp/llm01-prompt-injection.md` documents this as
the highest-leverage attack surface in agent code. The N=3 evidence
suggests the skill teaches Claude to recognize the surface across
distinct pattern shapes (response-cycling, fan-out, recursion).

**Finding 3 — V_clean scope must match catch scope (methodology
lesson).** First-pass V_clean for the two stretch samples fixed only
the bounded-loop OWASP risk (`LLM06`), reasoning that this was the
"stretch-specific" risk. The skill caught LLM01 prompt-injection
variants in both samples too, so V_clean v1 had precision = 0/4.
V_clean v2 (committed) added comprehensive `sanitize()` to inputs
and LLM-emitted fields. Lesson: V_clean must be a comprehensive fix
for every OWASP risk the skill identifies, not just the headline
risk. An incomplete V_clean is a V_clean defect, not a skill defect.

**Finding 4 — Skill rule consistency gap (future work).**
`rules/patterns/iterative-agent.md` Invariant 1 (bounded recursion)
explicitly accepts a throwing fix via `assertThatThrownBy`. Invariant
2 (LLM-determined fan-out cap) uses bare `verify(atMost(...))` with
no try/catch — which means a throwing V_clean errors out the test.
We worked around this by truncating in `OrchestratorWorkers_fixed.java`.
The skill rule should accept either fix style; this is on the
future-work list.

### Limitations and where the project breaks down

- **N=3 is existence proof, not benchmark.** Universal claims
  ("skill > vanilla on all Java AI code") would need N=15+ across
  more patterns + frameworks. Out of scope for a Week-7 deliverable.
- **Self-selected samples.** We chose iterative-agent variants
  precisely because the skill has unvalidated rules for them.
  `tool-handler`, `log-handler`, MCP server patterns are **not**
  end-to-end validated in Phase 2.
- **Maven-only.** The skill shells out to `mvn test-compile` and
  `mvn test`. Gradle, Bazel, or non-Maven projects fall outside
  the skill's verification step.
- **Java-only.** No Kotlin, no Scala, no other JVM languages.
- **Spring AI 1.0 fluent API only.** The chatclient-mocking rule
  encodes Spring AI's specific `ChatClient.prompt().user(...).call()`
  shape. LangChain4j and raw MCP clients have different APIs; the
  rule covers Spring AI primarily.
- **Catch-criterion regex applied with manual spot-check** for false
  positives (none found in N=3). Allowed to drop false catches but
  not add new ones.

## 6. Example inputs and findings

### Example 1 — `ChainWorkflow.java` (Phase 2 anchor)

**Real upstream OWASP risk**: line 121
`String input = String.format("{%s}\n {%s}", prompt, response);`
followed by `response = chatClient.prompt(input).call().content();`.
User input lands in step 0's prompt verbatim; the LLM response
cycles into step 1's prompt; both surfaces unsanitized.

**Expected risk**: LLM01 Prompt Injection (direct + indirect via
response cycling).

**Skill output** (5 tests, abridged): 4 attack-payload tests asserting
that `}}` / `<|im_start|>` / `[INST]` / `Ignore above` payload chars
do not survive into any captured prompt across the chain; 1 sanity
test asserting the chain makes 4 LLM calls (one per `DEFAULT_SYSTEM_PROMPTS`
entry). 4/4 catch on V_buggy; 5/5 PASS on V_clean.

**Vanilla output** (5 tests): all behavior-match. Test #3 uses the
same `ArgumentCaptor.getAllValues()` recipe but asserts the *literal
current format* `"{PROMPT_A}\n {USER_INPUT}"` — which means it locks
in the buggy behavior. 0/5 catch.

### Example 2 — `OrchestratorWorkers.java` (Phase 2 stretch)

**Real upstream OWASP risk**: line 189
`orchestratorResponse.tasks().stream().map(...)` streams over an
LLM-controlled `tasks` list with no upper bound — a poisoned or
runaway orchestrator response can spawn arbitrary worker LLM calls.
Plus `taskDescription` and `task.type/description` flow raw into
prompt parameters.

**Expected risks**: LLM06 / ASI08 (cascading failures), LLM01 / ASI07
(inter-agent communication).

**Skill output** (4 tests): template-breakout via user task,
`<|im_start|>` markers via orchestrator-emitted Task fields, Llama
`[INST]` tags via Task fields, **mock LLM emits 1000 tasks → assert
worker count is capped**. 4/4 catch on V_buggy; 4/4 PASS on V_clean.

**Vanilla output** (7 tests): all behavior-match. None mock a
1000-task response; none inject template-breakout payloads. 0/7
catch.

### Example 3 — `EvaluatorOptimizer.java` (Phase 2 stretch)

**Real upstream OWASP risk**: lines 212–235 are an unbounded
recursive `loop()` whose only exit is `evaluation == PASS`. An
evaluator that never returns PASS triggers `StackOverflowError`.
Evaluator `feedback` flows into next-iteration `context` raw.

**Expected risks**: LLM06 / ASI08 (bounded recursion), LLM01 indirect
/ ASI04 (poisoned feedback re-injects into generator context).

**Skill output** (4 tests): template-breakout via user task, OpenAI
markers via user task, **evaluator returns NEEDS_IMPROVEMENT with
poisoned feedback → assert second-iteration context does not leak
markers**, **evaluator never returns PASS → assert call terminates
within bounded LLM-call count**. 4/4 catch on V_buggy; 4/4 PASS on
V_clean.

**Vanilla output** (7 tests): all behavior-match. Tests assert
specific 3-iteration sequences, not bounded termination. 0/7 catch.

### Anticipated failure cases

The pre-pivot engine eval (§ 8) explicitly enumerated six failure
modes (hallucinated assertion, tautological assertion, OWASP
miscategorization, compilation failure, pattern library staleness,
over-suggestion). The skill-era equivalents:

| Failure mode | Mitigation in skill workflow |
|---|---|
| Hallucinated assertion | mvn test on V_buggy + V_clean — V_clean run catches assertions that fail even on clean code |
| Tautological assertion | rules/general/attack-payload-assertions.md mandates that tests assert payload non-survival, not literal format equality |
| Pattern misclassification | SKILL.md Step 1 refuses if no pattern matches; doesn't fall back to a generic mode |
| Compilation failure | SKILL.md Step 6 retries `mvn test-compile` up to 5 times, surfaces unfixable failures honestly |
| Pattern library staleness | 12 markdown files version-controlled; date-stamped (rules cite "verified 2026-05-07") |
| Over-suggestion | SKILL.md Step 4 asks user to confirm test cases before generation |

## 7. Risks and governance

**Where the system can fail.**

- OWASP risk → Java pattern mapping is novel and may be incomplete
  beyond the 4 patterns / 3 risk classes covered.
- The N=3 result is N=3 — the framing differential may not generalize
  to all Java AI agent code.
- Spring AI / LangChain4j / MCP all change rapidly; the
  `rules/java/chatclient-mocking.md` rule encodes Spring AI 1.0's
  specific fluent API and will need updates when 2.x lands.
- Maven-only verification.

**Where the system should not be trusted.**

- As a replacement for human security review of agent code.
- For OWASP risks outside the curated category list (the skill
  refuses on unrecognized site types).
- For programming languages other than Java.
- For non-agent Java code (the skill has no useful patterns to apply).

**Controls (where a human stays involved).**

- **Always human-in-the-loop.** Every generated test class is
  advisory; SKILL.md Step 7 explicitly states "do NOT write to
  `src/test/java/` without explicit user confirmation". **No
  generated test is ever auto-merged into a project.**
- **Mandatory OWASP citation.** Every emitted test method's javadoc
  cites a specific OWASP risk ID. Tests citing nothing are dropped
  in review.
- **Two-phase verification.** SKILL.md Step 6 runs `mvn test-compile`
  (catches uncompilable output) AND `mvn test -Dtest=<…>AgentGenTest`
  (catches assertions that fail on the user's actual code without
  injection). Failures are reported, not hidden.
- **Refusal as first-class output.** When no agent pattern is
  identified at Step 1, SKILL.md says: refuse with "no agent pattern
  detected; AgentTest does not apply." No fabrication.
- **Pattern library as version-controlled markdown.** All 12 rule
  files live in `claude-skill/agenttest/rules/`, diff-reviewable.

**Data, privacy, cost.**

- *Privacy*: AgentTest does **not** collect, log, or persist any
  user data. The Java source is read by Claude Code as the user's
  own session would read any file. **No second LLM provider call.**
- *API keys*: **none required.** Skill-native architecture means the
  user's existing Claude Code subscription covers all LLM calls. The
  README explicitly states this.
- *Cost*: $0 marginal — uses the user's Claude Code subscription.
- *Reproducibility*: `git clone` → `bin\install-skill.ps1` →
  `/agenttest <file>` in any Claude Code Maven Java project. README
  walks the grader through end-to-end on one example.

## 8. Sprint history (S1–S5, Weeks 4–8)

| S | Week | What happened |
|---|------|---------------|
| **S1** | 4 | Repo skeleton: pyproject + agents wiring, analyzer with 1 risk-site rule, retriever stub, generator stub. End-to-end FastAPI engine pipeline runs on 1 example, emits a dummy JUnit method. |
| **S2** | 5 | Real generator prompt for LLM01. OWASP catalog YAML with 4 risks. Validator (parse + compile + clean-input check). 5 hand-built test cases. First recall numbers (4/6 = 66.7%). |
| **S3** | 6 | **Course Week-6 check-in.** Agent-pattern retrieval added. Baseline endpoint live. Test set expanded to 6 cases. Headline: pipeline 4/6 = baseline 4/6 — same recall, **different failure modes** (pipeline drops at validator gate; baseline ships wrong-invariant tests). |
| **S4** | 7 | **Mid-sprint architecture review pivots from engine to skill-native.** Engine deleted (commit `99df6e0`). Skill scaffold + 12 modular rules authored. Phase 2 real-world eval on `ChainWorkflow.java` (anchor) + `OrchestratorWorkers.java` + `EvaluatorOptimizer.java` (stretch) — N=3 final headline 12-0. README + project_plan rewrite. |
| **S5** | 8 | (Planned) Lightning presentation slides. README final pass. Demo clip. (Optional polish: log-handler validation, MCP target validation.) |

### S4 pivot rationale (abridged from sprint-4.md § "Why pivot")

S1–S3 built a complex engine pipeline assuming "skill = wrapper
around external service". A mid-S4 review surfaced four problems:

1. **Self-validation problem.** S2/S3 wrote samples knowing what bug
   to inject, then tested catch on the same samples. Closed loop,
   weak credibility.
2. **Validator gate's classpath was fixture-specific.** Real Spring
   AI users compile against actual Spring AI jars via mvn — the
   stub-only validator was testing a world the user never lives in.
3. **Product surface unclear.** A FastAPI server isn't user-facing.
4. **Skill design philosophy mismatch.** Claude Code skills are
   prompt-time augmentation, not external LLM services. The
   architecture "skill → CLI → engine → Anthropic API" defies skill
   conventions and forces a second API key on the grader.

S4 pivoted to skill-native exclusively. The engine (~5000 lines
Python + ~200 Java + the synthetic eval harness) was deleted in
commit `99df6e0`. Methodological rigor is preserved by mechanical
clean-vs-buggy `mvn test` PASS / FAIL on real OSS code — no human
eval, no model-as-judge.

The pre-pivot engine code is recoverable from git history at any
commit before `99df6e0` (e.g., `git show 4359ac7:engine/...`). The
S2/S3/S4 sprint plans (gitignored under `docs/plan/`) carry the
detailed phase tracking, locked decisions, and pre-pivot artifact
disposition for archeology when needed.

## 9. Pair request

N/A — individual project.
