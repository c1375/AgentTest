# AgentTest — Project Plan

## 1. Project title

**AgentTest** — security-aware unit test generator for Java AI agent code.

## 2. Target user, workflow, and business value

**Who.** A Java developer building an AI-agent product on the Spring AI /
LangChain4j / MCP stack. The primary persona is an individual engineer or
a small team that owns a multi-tenant agent codebase and writes JUnit
tests for their own code. The design is anchored on a real Spring Boot multi-tenant
agent codebase the author maintains, but **that codebase is not part of
the deliverable, never sees the grader, and never enters the eval set**;
AgentTest is evaluated only on synthesized samples (see § 5).

**Recurring task.** Writing unit tests for newly written or modified agent
code. The painful subset is *security-relevant* tests: tests that catch
prompt-injection vectors in template assembly, tool-schema/implementation
mismatches, sensitive-data leakage into prompts or logs, multi-tenant
boundary violations, and retry / circuit-breaker misconfigurations. These
are precisely the categories in OWASP Top 10 for LLM Applications, OWASP
LLMSVS, and OWASP Top 10 for Agentic AI. General-purpose AI test
generators (TestSpark, MutGen, ChatUniTest, Diffblue) optimize for line
coverage and mutation score on generic code; they have no risk taxonomy
and no Spring-AI-specific knowledge, so they consistently miss this class
of bug.

**Where the workflow begins and ends.** The workflow begins when the
developer points AgentTest at a Java class implementing agent logic
(`MenuMcpServer.java`, `RestaurantPromptAssembler.java`, etc.). It ends
when the developer has reviewed a generated JUnit 5 test class file and
either accepted it into `src/test/java/...` or rejected it. **Generated
tests are advisory only — a human must review every test before it
lands**, both because LLM-written tests can lock the wrong invariant and
because the course assignment's "where a human should stay involved"
section requires this control to be explicit.

**Why better performance on this workflow matters.** Agent code is
disproportionately exposed to a class of bugs that traditional Java code
is not — prompt injection, tool abuse, sensitive-data leakage, multi-
tenant boundary failures. These bugs are also disproportionately *invisible*
to traditional test suites (which test functional correctness, not
adversarial robustness). Closing the gap between "what general AI test
generators write" and "what an agent codebase actually needs to test"
saves the developer hours per week of writing risk-specific tests by
hand and lowers the probability of an OWASP-class bug shipping unnoticed.

## 3. Problem statement and GenAI fit

**The exact task.** Given a Java source file containing AI-agent logic,
emit a JUnit 5 test class. Each generated test method must:

1. Target a specific OWASP risk by ID (e.g., `LLM01_Prompt_Injection`)
2. Cite a specific line range or method in the input class as the target
3. Produce JUnit 5 + Mockito assertions that **fail when the named risk
   is realized in the code, and pass when the code is clean**
4. Compile against a standard Spring Boot Test classpath

**Why GenAI.**

- OWASP risk descriptions are in English with implicit semantic context
  (e.g., LLM01: *"Prompt Injection occurs when user prompts alter the
  LLM's behavior or output in unintended ways…"*). Mapping that to a
  specific Spring AI prompt-template assembly call site requires language
  understanding — not keyword matching, not static analysis pattern rules.
- Generating valid JUnit 5 + Mockito source that **tests behavior under
  adversarial input** is unambiguously generation. The assertion must
  capture an invariant the LLM *infers* from the OWASP risk description
  applied to the *specific* Java code. No template-based generator can
  do this.
- Avoiding the *tautological assertion* failure mode (LLM writes a test
  that asserts "the code does what the code does") requires reasoning
  about *contract* — what the function *should* do under attack —
  separately from *implementation*.

**Why simpler alternatives fall short.**

- Static analyzers (SpotBugs / SonarQube / SemGrep) can flag patterns but
  cannot emit executable JUnit tests, and their rule libraries do not
  cover OWASP LLM categories.
- Template-based test generators (Auto-Unit-Test-Case-Generator and
  similar) produce coverage-driven boilerplate, not risk-targeted
  adversarial tests.
- General LLM test generators (TestSpark, ChatUniTest, MutGen, Qodo
  Cover) optimize for line coverage and mutation score on generic code.
  Their evaluation benchmarks (HumanEval-Java, LeetCode-Java, Defects4J)
  contain no agent code and no OWASP-class bugs. They write tests that
  pass on prompt-injection-vulnerable code because that code "works"
  functionally.
- Runtime LLM red-teaming tools (Garak, Augustus, Spikee, AutoRedTeamer)
  probe deployed systems; they do not generate unit tests against
  source code, and they cannot test code that has not been deployed.

The intersection — *source-level, OWASP-aligned, Java-agent-specific,
JUnit-emitting* — is empty in the prior art, despite this being a
recurring pain point publicly acknowledged in the Spring AI / agent-
development community.

**Use of RAG, justified.** The assignment forbids RAG / multi-model
pipelines unless they demonstrably help. Our retrieval over the OWASP
risk catalog and the agent-pattern library is justified because (a) the
OWASP catalog is too long to fit cleanly in every prompt; (b) the
agent-pattern library teaches the LLM to recognize Spring AI / LangChain4j
/ MCP idioms in the input. **Whether either retrieval source actually
helps is a first-class evaluation question** — see § 5 ablation. If a
retrieval source does not measurably improve recall, it gets dropped
from the deliverable.

## 4. Planned system design and baseline

### Architecture

```
Java source file (one class)
    │
    ▼
[Analyzer]              JavaParser AST → list of "risk-relevant sites":
                        prompt-template assembly, tool handler signatures,
                        MCP transport boundaries, retry/CB config, tenant
                        boundary methods. NO LLM here — deterministic.
    │
    ▼
[Retriever]             For each (site, candidate-OWASP-risk) pair, fetch:
                        - OWASP risk catalog entry (description + exemplar)
                        - 1–3 agent-pattern examples from curated library
                        - (optional) project-local context (CLAUDE.md)
    │
    ▼
[Generator]             Claude Sonnet 4.6 prompted per (site, risk) pair.
                        Output schema:
                        { risk_id, target_lines, test_method_source,
                          assertion_rationale, refused?: bool }
                        Refusal allowed when no test would meaningfully
                        target the risk on this site.
    │
    ▼
[Validator]             Parse-check (JavaParser) and compile-check
                        (javac in-memory). Drop tests that:
                        - fail to compile
                        - fail to run on the clean input (would always-fail)
    │
    ▼
[Aggregator]            Combine surviving methods into one JUnit 5 test
                        class; resolve imports; emit single .java file.
    │
    │  served from FastAPI :8000 via SSE (progress events)
    │  primary surface: CLI (used by grader and eval harness)
    │  bonus surface:   Claude Code skill (optional, interactive)
    ▼
JUnit 5 source written to user-specified path
```

### Stages

1. **Analyzer.** Pure Java AST analysis. Identifies risk-relevant sites
   using deterministic pattern rules (e.g., a method that takes a `String`
   parameter and constructs a `PromptTemplate` is a candidate prompt-
   assembly site for LLM01). Outputs a list of `RiskSite` records with
   file path, line range, and candidate OWASP risk IDs. **No LLM call
   in this stage** — keeps the per-class cost low and the analyzer
   deterministic / cacheable.

2. **Retriever.** For each `RiskSite`, retrieves:
   - The OWASP catalog entry for each candidate risk (from
     `configs/owasp.yaml` — a curated YAML of ~10 risks we cover, each
     with description, exemplar Java pattern, and exemplar test pattern)
   - 1–3 closest agent-pattern examples from a curated library
     (`configs/patterns/{spring-ai, langchain4j, mcp}/...`) by
     embedding similarity on the site's surrounding context
   - (Optional) project CLAUDE.md, CONTRIBUTING.md sections — only
     fetched if the user provides a `--project-root` flag

3. **Generator.** Per (site, risk) pair, one Claude Sonnet 4.6 call with
   a structured prompt:
   - System: role definition + JUnit 5 + Mockito conventions
   - User: OWASP risk description, agent-pattern examples, the target
     site's source, the invariant to assert
   - Output: structured JSON with `risk_id`, `target_lines`,
     `test_method_source`, `assertion_rationale`, optional `refused`
   The model is hard-required to either emit a test that *fails on
   demonstrably risky variants of the site* or refuse. Bail-out is a
   first-class output, not a fallback.

4. **Validator.** Parse the generated `test_method_source` with
   JavaParser; reject if not valid Java. Compile in-memory against a
   stub classpath; reject if compile fails. Run the compiled method
   against the clean input class; reject if it fails on the clean
   input (means the assertion is wrong, not just the code is risky).

5. **Aggregator.** Collect surviving test methods into one class with
   a stable name (`<TargetClass>SecurityGenTest.java`), proper imports,
   and a header comment listing OWASP risk IDs covered.

### What the user sees and does

**Primary surface (grader-facing): a CLI.**
`python -m agenttest.cli generate path/to/Foo.java [--out FooSecurityGenTest.java]`
reads the Java source, streams progress lines while the pipeline runs
(`analyzing → retrieving → generating → validating`), and writes one
JUnit 5 test class. The README walks the grader through one risk-injected
example end-to-end. **The CLI is what the assignment is evaluated against.**

**Bonus surface (planned for S5 if scope permits): a Claude Code skill.**
`/agenttest analyze Foo.java` would wrap the same FastAPI engine and surface
SSE progress events into Claude Code's terminal. The skill is a
developer-experience improvement; **the grader does not need to install
Claude Code** to evaluate the project — the CLI is the deliverable.

### How the course concepts show up

The assignment requires at least two; the design naturally lands on four.

**1. Multi-step orchestration (Week 5).** Five-stage pipeline:
`analyzer → retriever → generator → validator → aggregator`. Each stage
has a typed input/output contract; stages compose via Protocols, not
shared state. This decomposition is what makes the ablation matrix in § 5
possible — each row drops or replaces a single stage.

**2. Retrieval-Augmented Generation (Week 4).** Two retrieval sources:
the OWASP risk catalog (~10 risks, ~200 tokens each) and the agent-pattern
library (~30 patterns, ~150 tokens each). Both stored as YAML plus an
embedded index built with `sentence-transformers/all-MiniLM-L6-v2`
(local; ~80 MB one-time download, no extra API key). Per risk site,
retrieve top-3 from the pattern library and matched OWASP entries, pack
into the generator prompt. **Whether RAG (vs. stuffing the full catalog
in every prompt) actually helps is empirically tested by ablation** —
see § 5.

**3. Structured outputs (Weeks 2–3).** The generator does not return free
text. It returns a JSON object validated against
`{ risk_id, target_lines, test_method_source, assertion_rationale, refused?: bool }`.
This makes refusal a first-class output (not a free-text sentence the
parser has to detect), lets the validator gate `test_method_source` in
isolation, and gives the eval harness a deterministic field to scan for
the OWASP risk ID.

**4. Governance and deployment controls (Week 6).** The plan ships with
explicit human-in-the-loop framing (every test is advisory; never
auto-merged), mandatory OWASP citation per emitted method (untraceable
tests are dropped), a validator gate (compile-fail or clean-input-fail
tests are dropped before the user sees them), and refusal-as-output
(empty test class with explanatory comment when no risk site is
identified). See § 7 for the full controls list.

### Baseline

**Baseline = single-prompt Claude Sonnet 4.6.** Implemented as a sibling
endpoint `POST /generate/baseline` in the same FastAPI app. Takes the
same Java class, sends a single prompt of the form:

> *"You are a security-focused Java test engineer. Given the following
> Java class implementing AI-agent logic, generate JUnit 5 + Mockito
> tests targeting common OWASP risks for LLM agents. Output one Java
> test class file."*

No analyzer, no retrieval, no per-risk loop, no validator. The eval
harness calls both endpoints (`/generate` and `/generate/baseline`)
on the same test cases. The baseline is *fair* because it is what a
developer using Claude alone would produce — same model, same input,
same output format expectation.

## 5. Evaluation plan

### Ground truth: synthetic injection

For each clean Java sample, we define one or more **risk injections** —
deterministic edits that introduce a known OWASP-class bug:

- LLM01 (Prompt Injection): remove input sanitization in a prompt
  template; concatenate raw user input into a template string
- LLM02 (Sensitive Information Disclosure): inject `log.info(request)`
  on a path that may contain secrets
- LLM06 (Excessive Agency): make a tool's declared description claim
  read-only behavior while the implementation writes
- Agentic-AI: remove the tenant-ID validation before a privileged tool call
- Resilience-related: misconfigure Resilience4j retry to permit unbounded
  retry attempts on a transient-error class

For each (clean sample, injection) pair, AgentTest is run on **the buggy
variant**. The generated test class is compiled and run against:

- **The buggy variant** — at least one generated test should fail
  (true positive: catches the injected risk)
- **The clean variant** — no generated test should fail
  (true negative: no false positive)

This is **completely objective**. No model-as-judge for the primary
metric.

### Test set composition

~20 hand-curated clean Java code samples, distributed as:

- Spring AI prompt assemblers and `PromptTemplate` consumers (~6)
- LangChain4j tool definitions and tool handlers (~4)
- MCP server tool registrations and request handlers (~4)
- Multi-tenant agent code (tenant-scoped tool invocation) (~3)
- Resilience-related: retry / circuit breaker config call sites (~3)

For each clean sample, define 1–3 risk injections → **~30–50 test cases
total**. If sample synthesis runs slow we accept landing at the lower
end of the range (~15 samples / ~30 cases) for the Week 6 check-in.

The samples are synthesized from real OSS patterns (Spring AI examples,
LangChain4j docs, MCP spec examples) — no proprietary code.

### Metrics

**Primary (objective):**

- **Recall@class** (catch rate): percentage of injected risks for which
  at least one generated test fails on the buggy variant
- **Precision (false-positive rate)**: percentage of generated tests
  that fail on the clean variant — should be near zero
- **Per-OWASP-risk breakdown**: recall and precision separately per
  risk category (LLM01, LLM02, LLM06, etc.)

**Secondary:**

- **Compilation rate**: percentage of generated test methods that compile
- **Refusal correctness**: when no risk is present, does the system
  correctly refuse rather than fabricate a test
- **Latency**: seconds per Java class (target ≤ 60s)
- **Cost**: $ per Java class (target ≤ $0.10)

### Ablation matrix

| Configuration | Recall@class | Precision | Cost / class |
|---|---|---|---|
| Baseline (single-prompt, no retrieval, no analyzer) | | | |
| Analyzer only (no retrieval, generator gets raw site) | | | |
| Analyzer + OWASP catalog retrieval | | | |
| Analyzer + Agent-pattern retrieval | | | |
| Full system (Analyzer + both retrieval + validator) | | | |

Each row run on the full test set. **Component dropped if its row
shows no meaningful improvement over the row above** (ASSIGNMENT.md:
*"Do not use RAG, agents, or multiple models unless they actually help"*).

### Success thresholds

AgentTest is successful if, on the test set:

- Recall@class ≥ 60% (catches a majority of injected risks)
- Precision ≥ 80% (low false-positive rate on clean code)
- Beats the single-prompt baseline on recall by a measurable margin
  (≥ 15 percentage points)
- Stays within 60 seconds and $0.10 per Java class

If these thresholds are not met by the deliverable date, the README
will report what we did achieve, in which categories we underperformed,
and a hypothesis about why. Honest negative results are an assignment-
required output: *"what worked, what failed, where a human should stay
involved."*

## 6. Example inputs and failure cases

### Example inputs

1. **`RestaurantPromptAssembler.assemble(String userQuery)`** — a Spring
   AI prompt builder that interpolates `userQuery` into a multi-tenant
   system-prompt template. **Expected risk**: LLM01 Prompt Injection.
   Expected test: feed `userQuery` containing template-breakout content,
   assert assembled prompt does not contain the breakout.

2. **`MenuMcpServer.searchMenu(SearchRequest req)`** — an MCP tool
   handler whose tool description says "read-only menu search" but whose
   implementation increments a per-tenant view counter (writes).
   **Expected risk**: LLM06 Excessive Agency / Tool Description Mismatch.
   Expected test: assert the implementation's observable side effects
   are consistent with the tool description.

3. **`AgentLogger.logRequest(AgentRequest req)`** — logs the full
   `req.toString()`. **Expected risk**: LLM02 Sensitive Information
   Disclosure if `req` carries headers or user-attributed data. Expected
   test: feed a request with sentinel-PII fields, assert logged output
   does not contain them.

4. **`OrderTool.execute(String tenantId, OrderArgs args)`** — privileged
   tool that does not validate `tenantId` matches the calling session's
   tenant. **Expected risk**: Multi-tenant boundary violation
   (OWASP Agentic-AI category). Expected test: invoke with mismatched
   tenant, assert refusal.

### Anticipated failure cases

1. **Hallucinated assertion** — generated test asserts an invariant that
   does not hold even on clean code. *Mitigation*: validator drops tests
   that fail on the clean variant.

2. **Tautological assertion** — test asserts what the code currently does
   (locking buggy behavior in). *Mitigation*: prompt explicitly demands
   the test target a *named OWASP risk*, with the risk description as
   the contract reference. The risk description is the oracle, not the
   implementation.

3. **OWASP miscategorization** — analyzer flags a site as risk type X
   when it is type Y. *Mitigation*: per-risk recall breakdown in eval
   surfaces the bias; analyzer emits multiple candidate risks per site
   and the generator picks the strongest.

4. **Compilation failure** — generated code uses an import or symbol
   that does not exist. *Mitigation*: validator's compile-check drops
   uncompilable methods before aggregation.

5. **Pattern library staleness** — Spring AI / LangChain4j / MCP all
   evolve fast; cached patterns may go stale. *Mitigation*: pattern
   library lives in version-controlled YAML (`configs/patterns/...`),
   diff-reviewable; date-stamped.

6. **Over-suggestion** — emits a flood of low-quality tests instead of
   a small set of strong ones. *Mitigation*: hard cap of one test per
   (risk site, OWASP risk) pair; validator drops the rest.

## 7. Risks and governance

**Where the system can fail.**

- OWASP risk → Java pattern mapping is novel and may be incomplete
- Synthetic injection eval may overstate real-world recall (controlled
  bugs are easier than real ones)
- Java AST parsing in Python ecosystem is less mature than in Java —
  fallback options: subprocess-call to a small Java helper that emits
  AST as JSON, or use `javalang` (pure-Python parser, less accurate)
- Spring AI / LangChain4j / MCP all change rapidly; pattern library
  drifts

**Where the system should not be trusted.**

- As a replacement for human security review of agent code
- For OWASP risks outside the curated category list (the system
  refuses on unrecognized site types)
- For programming languages other than Java
- For non-agent Java code (the system has no useful patterns to apply)

**Controls.**

- **Always human-in-the-loop.** Every generated test class is *advisory*;
  the README and CLI output state this on every run (and the skill UI as
  well, when used). **No generated test is ever auto-merged into a project.**
- **Mandatory OWASP citation.** Every emitted test method cites a
  specific OWASP risk ID. Tests citing nothing are dropped.
- **Validator gate.** No test that fails to compile, or fails on the
  clean input, reaches the user.
- **Refusal as first-class output.** When no risk site is identified,
  AgentTest emits an empty test class with an explanatory comment —
  never invents a risk to fill space.
- **Pattern library as version-controlled config.** OWASP catalog and
  agent-pattern library live in `engine/configs/`, diff-reviewable.

**Data, privacy, cost.**

- *Privacy*: AgentTest does **not** collect, log, or persist any user
  data. The submitted Java source is, however, **transmitted to Anthropic**
  for the Sonnet call. The README states this explicitly so users with
  proprietary code can make an informed choice before running the tool.
  The pattern-library RAG runs locally (sentence-transformers embedding,
  no second provider).
- *API keys*: the README documents the one key the grader needs to set
  in `.env` to reproduce — `ANTHROPIC_API_KEY` (required for generation).
  No other provider key is needed.
- *Cost*: ~$0.05–0.10 per class generation; **≤ ~$20 per full ablation
  run** (5 ablation rows × ~50 cases × ~$0.05–0.10 per call, with
  prompt-cache hits on the synthesizer's system prompt). Within personal
  budget; tracked per run so the budget can be tightened if needed.
- *Reproducibility*: `cd engine && pip install -e ".[dev]" && pytest`
  for unit tests; `python -m agenttest.cli generate <file.java>` for
  end-to-end run on one example. README walks the grader through.

## 8. Sprint plan

The course timeline is Week 4–8; this plan uses S1–S5 numbering.

| S | Week | Goal |
|---|------|------|
| **S1** | 4 | Skeleton: pyproject + agents wiring (already in place after rename), analyzer with 1 risk-site rule (prompt assembly), retriever stub, generator stub. End-to-end pipeline runs on 1 example, emits a dummy JUnit method. |
| **S2** | 5 | Real generator prompt for LLM01. OWASP catalog YAML with 4–5 risks. Validator (parse + compile). 5 hand-built test cases. First recall numbers. |
| **S3** | 6 | **Course Week-6 check-in.** Agent-pattern retrieval for Spring AI (highest leverage on the worked-example codebase). Baseline endpoint live. Test set expanded to ~15 cases. First baseline-vs-AgentTest comparison numbers. |
| **S4** | 7 | Test set to 30–50 cases. Full ablation matrix. Second-pass on weakest risk categories. CLI polish. **README first draft** (clone → run on one example). Pre-recorded demo clip captured. |
| **S5** | 8 | README final pass. Lightning presentation slides. Final eval run, final numbers. (Optional) Claude Code skill polished as bonus surface — only if the CLI + README are already grader-ready. |

By the **course Week-6 check-in**, we expect a working end-to-end
pipeline on ≥ 15 test cases, ≥ 3 OWASP risks covered, baseline endpoint
live, and rough recall/precision numbers — even if the eval is not yet
fully ablated. The point of Week 6 is to *have a credible measurement*,
not to win on every dimension.

**Lightning demo & artifact snapshot.** The 2–3 minute slide deck
includes one **pre-recorded ~30-second clip**: CLI run on one
prompt-injection sample → generated test class shown → the same test
fails on the buggy variant, passes on the clean variant. The README
mirrors this as a sample-input / sample-output block. ASSIGNMENT.md
does not require a live demo for the lightning presentation; the
pre-recording is the safety net, but a CLI run is short enough to
attempt live if time allows.

## 9. Pair request

N/A — individual project.
