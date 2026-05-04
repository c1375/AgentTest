# Sprint 3 Plan

S3 closes the gap to the **Week-6 course check-in**. After S2 we have one
OWASP risk (LLM01) measured end-to-end on 2 samples with Recall@class
= Precision = 100%. The Week-6 narrative needs ≥ 3 risks with first
baseline-vs-AgentTest comparison numbers.

> Source-of-truth scoping line, copied from `docs/project_plan.md` § 8:
> *"Course Week-6 check-in. Agent-pattern retrieval for Spring AI
> (highest leverage on the worked-example codebase). Baseline endpoint
> live. Test set expanded to ~15 cases. First baseline-vs-AgentTest
> comparison numbers."*

This plan deviates from § 8 on **sample count** (we hit 6, not 15) but
holds the **risk-coverage line** (≥ 3 OWASP risks). See "Why breadth
over depth" below for why this swap is the right one.

---

## Why breadth over depth (this time)

S2's adversarial review concluded "depth over breadth" because the
**methodology was unproven** — committing to 4 risks while not knowing
if any of them measured cleanly was a recipe for 4 half-finished
risks. S2 proved the methodology on LLM01.

S3's adversarial review concluded the opposite: **the methodology is
proven; the missing demonstration is that it generalizes across
risks**. The project's central claim is:

> *"Agent code has a CLASS of bugs (the OWASP Top 10) that traditional
> tests miss."*

Demonstrating coverage on **two** risks doesn't prove "a class" — it
proves "two cases." Three risks, especially three with materially
different test shapes, makes the class argument land.

The sample count (6, vs. project_plan.md's ≥ 15 target) is the
deliberate trade. The README + check-in narrative will be honest:
*"Risk-coverage breadth on the agent-specific OWASP categories,
sample-count growth deferred to S4."*

### What changed from the previous draft of this doc

The first draft picked LLM02 (Sensitive Information Disclosure) as the
second risk. Adversarial review found two problems:

1. LLM02 needs log-capture infrastructure (a `TestLogHandler` shim,
   maybe a SLF4J ↔ JUL bridge) — call it 1.5–2 days of
   non-risk-specific plumbing.
2. LLM02 isn't even **agent-specific**: PII-in-logs is a generic
   web-app problem. It doesn't differentiate AgentTest from any
   other testing tool.

LLM06 (Excessive Agency / Tool Description Mismatch) is materially
cheaper *and* more agent-specific:

- Test shape: state-snapshot → call method → state-snapshot — pure
  AssertJ comparison, **no log-capture infrastructure**.
- Injection: add a write to a method whose tool description says
  "read-only" — one-line edit.
- The risk itself only exists in agent code where a tool description
  is consumed by an LLM as ground truth.

That savings (~2 days vs. LLM02) opens the budget to **also** ship
LLM02 in S3 — a simpler version using `java.util.logging` directly,
deferring the SLF4J shim until S4 if grader feedback flags realism.
Net: S3 covers 3 risks at the same total cost as the first draft's
1-new-risk plan.

---

## Locked decisions

### 1. S3 OWASP coverage = LLM01 (existing) + LLM06 + LLM02

- **LLM01** stays as the established case (2 samples).
- **LLM06** (Tool Description ↔ Implementation Mismatch) is the
  primary new risk. State-snapshot test, no extra infrastructure.
- **LLM02** (Sensitive Information Disclosure) ships in a simplified
  form: samples use `java.util.logging.Logger` directly (less
  realistic than SLF4J but no shim work). The full SLF4J path
  becomes an S4 polish item if anyone notices.
- **Agentic_Multi_Tenant** moves to S4 entirely.

### 2. Sample count = 6 (2 LLM01 + 2 LLM06 + 2 LLM02)

Two samples per risk gives us:
- Per-risk recall variance: with N=2, 0%/50%/100% are the only
  measurements, but that's enough at this stage to spot a
  catastrophic miss.
- Cross-risk consistency: same prompt + same pipeline against three
  different invariant shapes lets us see whether one risk
  underperforms.

S4 expands each risk to ~5 samples (≥ 15 total) and adds the fourth
risk.

### 3. Baseline endpoint = `POST /generate/baseline` on the existing FastAPI app

Same architecture as `docs/project_plan.md` § 4: single Anthropic call,
no analyzer / retrieval / per-risk loop. The eval runner gains a
`--baseline` mode that calls this endpoint instead of `pipeline.run`.
Both modes feed the **same runner-helper** for recall / precision
measurement.

### 4. Step 0 = empirically check baseline's classpath behavior BEFORE locking the prompt

The first draft of this plan assumed baseline would emit Mockito
imports → COMPILE_FAIL → unfair "0% baseline." That was a prediction.
The cheapest way to stop predicting is to run one baseline call
($0.05) and read the output. The Step 0 result determines whether the
baseline prompt needs a "no Mockito" constraint, or whether Sonnet
naturally writes Mockito-free tests on these samples.

### 5. Pattern library still empty in S3

S2's "Locked decision 4" stands. No retrieval-over-patterns until
ablation (S4) proves it helps.

### 6. Prompt-cache stays disabled

S2 system prompt was ~400 tokens with one OWASP entry. S3 grows the
catalog to three entries (~1200 tokens), which **just barely** crosses
Anthropic's ~1024-token cache minimum. **Don't re-enable in S3** —
the marginal cache benefit on a per-pair basis is small (we only loop
within one risk per site), and a flag flip is one-line in S4.

### 7. Comparison run = both modes on the same 6 samples

Single combined invocation: `py -3.13 eval/compare.py` runs pipeline
mode, then baseline mode, on the same 6 samples × 1 injection each.
Output is one `comparison-<ts>.json` with `pipeline`, `baseline`, and
`delta` sections. **This is the headline artifact for the Week-6
check-in.**

### 8. The Week-6 reframe is honest, not hidden

The README's Week-6 status section will read approximately:

> *"S3 lands 3 OWASP risks (LLM01, LLM06, LLM02) end-to-end with
> baseline-vs-AgentTest comparison numbers on 6 hand-curated samples.
> The original ≥ 15-case target slips to S4; risk-coverage breadth
> was prioritized over sample-count growth on the basis that
> demonstrating cross-risk generalization is the load-bearing claim
> of the project."*

No silent quiet downgrade of `docs/project_plan.md` § 8. The honesty
itself reads well at a course check-in.

---

## Open questions (resolve during implementation)

1. **Baseline classpath behavior.** Settled by Step 0.
2. **LLM06 analyzer rule discriminator.** `tool_handler` is already in
   the `SiteKind` Literal. The detection heuristic for "this is a
   tool handler with a description" likely matches `@Tool(description=...)`
   annotations or methods with a sibling `Tool` registration. We'll
   pin the heuristic when authoring the LLM06 samples — they're the
   ground truth for what the analyzer must detect.
3. **LLM02 logger handle inside the test.** With JUL, attaching a
   handler is a 2-line ritual. Sonnet might or might not do it
   correctly on the first try; the OWASP `exemplar_test` for LLM02
   needs to show the exact shape.

---

## Author / data work (do this first)

### A. `engine/configs/owasp.yaml` — add LLM06 and LLM02 entries

LLM06:

```yaml
- risk_id: LLM06_Excessive_Agency
  title: Excessive Agency / Tool Description Mismatch
  description: |
    A tool exposed to the LLM declares one capability surface in its
    description (e.g., "read-only menu lookup", "stateless weather
    query") while the implementation does additional, unannounced
    work — writing state, calling external APIs, mutating per-tenant
    counters. The LLM trusts the description verbatim and may compose
    actions assuming false invariants, leading to data leaks, billing
    surprises, or privilege escalation.
  invariant_to_assert: |
    For a tool whose description claims read-only or
    side-effect-free behavior, invoking the implementation MUST NOT
    change observable state outside the method (no writes to
    repositories, no counter increments, no cache mutations, no
    audit-log entries beyond the inbound trace).

    The simplest testable form: snapshot the relevant state before
    the call, invoke the method, snapshot again, assert the two
    snapshots are equal. The clean implementation must respect the
    description; the LLM06 injection violates it.
  exemplar_java: |
    public List<MenuItem> searchMenu(SearchRequest req) {
        viewCounter.increment(req.tenantId);   // BUG: not in description
        return menuRepo.findMatching(req.query);
    }
  exemplar_test: |
    @Test
    void searchMenuLeavesViewCounterUnchanged() {
        InMemoryViewCounter counter = new InMemoryViewCounter();
        MenuMcpServer server = new MenuMcpServer(counter, new InMemoryMenuRepo());
        long before = counter.snapshot("tenant-1");

        server.searchMenu(new SearchRequest("tenant-1", "pasta"));

        assertThat(counter.snapshot("tenant-1"))
            .as("a tool described as read-only must not increment view counters")
            .isEqualTo(before);
    }
```

LLM02 (the simpler JUL-based form):

```yaml
- risk_id: LLM02_Sensitive_Information_Disclosure
  title: Sensitive Information Disclosure
  description: |
    User-attributable input or context (PII, headers, secrets, prompt
    history) is logged at INFO/DEBUG level in a way that crosses a
    privilege boundary — the log sink (filesystem, ELK, third-party
    SaaS) is not in the same trust boundary as the original payload.
    A correct implementation redacts or omits sensitive fields
    before logging.
  invariant_to_assert: |
    For any input carrying a known PII sentinel (e.g.,
    `Authorization: Bearer SENTINEL_TOKEN`, `email:
    sentinel@example.com`, `ssn: 999-99-9999`), the log lines emitted
    during the method's execution MUST NOT contain that sentinel
    value verbatim. Test pattern: drive the method with a sentinel
    input, capture log output via `java.util.logging.Handler`,
    assert the captured output does not contain the sentinel.
  exemplar_java: |
    public void logRequest(AgentRequest req) {
        logger.info("Handling request: " + req.toString());  // BUG: leaks PII
    }
  exemplar_test: |
    @Test
    void doesNotLogAuthHeaderVerbatim() {
        TestLogHandler handler = new TestLogHandler();
        Logger logger = Logger.getLogger("com.example");
        logger.addHandler(handler);

        AgentRequest req = new AgentRequest();
        req.setAuthHeader("Bearer SENTINEL_TOKEN");
        new AgentLogger().logRequest(req);

        assertThat(handler.capturedText())
            .as("Authorization header must not appear verbatim in logs")
            .doesNotContain("SENTINEL_TOKEN");
    }
```

### B. `engine/eval/runner-helper/stubs/com/example/test/TestLogHandler.java`

~25-line `java.util.logging.Handler` subclass: captures log records
into a list, exposes them via `capturedText()` (concatenated record
messages). Lives in the runner-helper's `stubs/` so it compiles
alongside any LLM02 test. JUL only, no SLF4J — keeping it small.

### C. Four new sample Java files + meta.yaml

| # | Sample | Risk | Shape |
|---|---|---|---|
| 3 | `MenuMcpServer.java` | LLM06 | MCP tool handler with `@Tool(description="read-only menu search")`; clean implementation reads from `MenuRepo` only |
| 4 | `WeatherTool.java` | LLM06 | Spring AI `@Tool` returning weather; clean implementation queries the upstream API without caching |
| 5 | `AgentLogger.java` | LLM02 | Plain class with `java.util.logging.Logger`; clean implementation calls `redactPii(req)` before logging |
| 6 | `RequestAuditTrail.java` | LLM02 | Records each tool invocation; clean implementation hashes user-supplied arguments before logging |

Each gets a sibling `*.meta.yaml`. The LLM06 samples set
`applicable_injections: [llm06_add_unannounced_write]`; the LLM02
samples set `applicable_injections: [llm02_drop_redaction]`.

### D. Two new injection scripts

`engine/eval/injections/llm06_add_unannounced_write.py` — appends a
side-effect call (e.g., `counter.increment(req.tenantId);`) inside
the body of a method annotated `@Tool`. Brace-matching scan for the
method body, insert one line before the `return`.

`engine/eval/injections/llm02_drop_redaction.py` — replaces a call to
`redactPii(req)` (or similar named helper) with the raw `req`. Pattern
similar to `llm01_remove_sanitization.py` — both work by removing a
guard helper.

---

## Implementation deliverables (in dependency order)

### Step 0 — Baseline behavior smoke (do this first)

Cost: $0.05, time: 0.1 day.

Run a single ad-hoc baseline call against `RestaurantPromptAssembler.java`
with the exact prompt from `docs/project_plan.md` § 4. Read the
output. Decide:

- **If baseline emits Mockito imports** → we add a "no Mockito"
  constraint to the baseline prompt to keep classpath fairness.
  Document the constraint addition explicitly.
- **If baseline emits AssertJ-only or pure JUnit** → ship the prompt
  unchanged. Pipeline and baseline compete on the same surface.

Either way, the decision is empirical, not predicted. **Don't
proceed past Step 0 without doing this.**

### Step 1 — Analyzer rule for LLM06 (`tool_handler`)

`engine/src/agenttest/analyzer/identify.py`

Add a rule alongside the existing `prompt_assembly` rule. A method
qualifies as a `tool_handler` site if:

- It is annotated `@Tool` (any package), OR has a sibling field /
  registration that registers it as an MCP tool, AND
- The annotation's `description` attribute (or sibling registration's
  description) is non-empty.

Set `site_kind="tool_handler"`,
`candidate_risks=["LLM06_Excessive_Agency"]`. The existing analyzer's
position-extraction logic carries over.

Test: extend `engine/tests/test_analyzer.py` with one positive case
(class with `@Tool(description="...")` method) and one negative
(class with annotation-less method).

### Step 2 — Analyzer rule for LLM02 (`log_handler`)

Same module, same pattern. A method qualifies as a `log_handler` site
if:

- It takes ≥ 1 user-attributable parameter (any non-primitive
  reference type), AND
- Its body contains a method call whose receiver is a field/local of a
  type whose simple name ends in `Logger` or `Log`, with method name
  in `{info, warn, error, debug, log}`, with at least one argument
  that's a parameter (or contains a parameter as a sub-expression).

Set `site_kind="tool_handler"` (reusing the existing Literal value —
the OWASP risk `candidate_risks` is what carries the per-risk
discrimination), `candidate_risks=["LLM02_Sensitive_Information_Disclosure"]`.

Test: extend `test_analyzer.py` with positive + negative cases.

### Step 3 — Generator-side LLM06 + LLM02 smoke (real Sonnet)

The generator's prompt template is risk-agnostic — it threads the
right `OwaspEntry` from `grounding`. New risks should "just work" via
their catalog entries. Verify with two real-Sonnet smokes:

- LLM06 on `MenuMcpServer.java` → expect a state-snapshot test.
- LLM02 on `AgentLogger.java` → expect a `TestLogHandler`-attaching test.

If either smoke produces nonsense (cargo-culted class names, wrong
fixture API), iterate the catalog `exemplar_test` until it lands. We
budget 1 day total for prompt iteration across both risks (S2 needed
0.5 day on LLM01 — assume S3 is similar per risk).

### Step 4 — Baseline endpoint

`engine/src/agenttest/baseline/synthesize.py`:

```python
async def synthesize_baseline(
    java_source: str,
    target_class_name: str,
    client: AgentClient,
) -> BaselineEmission:
    """Single-prompt Sonnet, no analyzer/retrieval/per-risk loop."""
```

Prompt: the verbatim text from `docs/project_plan.md` § 4, possibly
with the Step-0-determined "no Mockito" addition.

`agenttest.contracts.BaselineEmission`:

```python
@dataclass(frozen=True)
class BaselineEmission:
    target_class_name: str
    java_source: str        # the LLM's raw output, expected to be a Java class
```

`engine/src/agenttest/http/routes.py` adds:

```python
@router.post("/generate/baseline")
async def generate_baseline(req: BaselineRequest) -> BaselineResponse:
    ...
```

with Pydantic request / response models. The eval runner can either
call this via local HTTP or via direct function call — the latter is
faster for offline eval, the former exercises the FastAPI surface.
S3 uses **direct function call** (faster, no uvicorn lifecycle); S4
or S5 wires the HTTP path explicitly when SSE comes in.

Tests: `engine/tests/test_baseline.py` with mocked AgentClient,
covering the happy path + the Java-extraction edge cases (Sonnet may
wrap the class in markdown fences, just like the structured generator).

### Step 5 — Eval runner gains baseline mode

`engine/eval/runner.py` gets a `mode` parameter:

```python
async def run_eval(
    samples_dir: Path = Path("eval/samples"),
    results_dir: Path = Path("eval/results"),
    mode: Literal["pipeline", "baseline"] = "pipeline",
) -> EvalResult:
    ...
```

Baseline mode skips `pipeline.run` and instead reads the clean Java +
calls `synthesize_baseline`. The result wraps as a synthetic
`TestClassEmission`-shaped object with `risks_covered=[]` (baseline
doesn't track per-risk) and `java_source = baseline_emission.java_source`.

The same validator gate (parse + run-on-clean) runs over the
baseline's output. Drops baseline tests that fail on clean.

The same recall / precision measurement runs over (clean, buggy)
variants — but we need to apply EVERY applicable injection for every
sample in baseline mode, since baseline doesn't know which risk it
was targeting. (For S3 with one injection per sample this is the
same number of pairs.)

Filenames: `run-pipeline-<ts>.json` and `run-baseline-<ts>.json`.

CLI: `py -3.13 eval/runner.py --baseline`.

Tests: extend `test_eval_runner.py` with a baseline-mode integration
test using a monkey-patched `synthesize_baseline`.

### Step 6 — Combined comparison run

`engine/eval/compare.py` (~80 lines): runs both modes back-to-back,
emits a single `comparison-<ts>.json`:

```json
{
  "timestamp_utc": "...",
  "pipeline": { ...pipeline EvalResult... },
  "baseline": { ...baseline EvalResult... },
  "delta": {
    "recall_at_class_pp": <pipeline.recall - baseline.recall>,
    "precision_pp":       <pipeline.precision - baseline.precision>,
    "samples_compared":   <int>
  }
}
```

Stdout summary:

```
Comparison complete: 6 pairs each
  Pipeline: Recall@class=83.3% | Precision=100.0%
  Baseline: Recall@class=33.3% | Precision=100.0%
  Delta:    +50.0 pp recall
```

This file is what the README links to as the Week-6 evidence.

### Step 7 — README update

The repo root `README.md` currently says "Status: Sprint S1 (Week 4)".
Replace with:

- Status: S3 complete; Week-6 check-in evidence linked
- One-paragraph summary of the comparison numbers (with link to the
  latest `comparison-*.json`)
- Updated "Setup" section reflecting `eval/runner.py --baseline` and
  `eval/compare.py`
- Cost note: a single full comparison run is ~$0.60 of Anthropic
  credits; a full S3-iteration cycle (smokes + tweaks + final run)
  is typically $5–10. Grader running `eval/compare.py` once: ≤ $1.

S5 polishes the README further; S3's update is "don't lie about
project state."

---

## Sequenced timeline (~9 days)

| Step | What | Estimate | Depends on |
|---|---|---|---|
| Step 0 | Baseline behavior smoke ($0.05) | 0.1d | — |
| Pre-S3 cleanup | (see below) | 0.5d | — |
| Author A | owasp.yaml LLM06 + LLM02 entries | 1d | — |
| Author B | TestLogHandler.java | 0.2d | — |
| Author C | 4 sample Java + meta.yaml | 1.5d | A |
| Author D | 2 injection scripts | 1d | C |
| Step 1 | Analyzer LLM06 rule + tests | 0.5d | C |
| Step 2 | Analyzer LLM02 rule + tests | 0.5d | C |
| Step 3 | LLM06 + LLM02 generator smokes (real Sonnet) | 1d | A, 1, 2 |
| Step 4 | Baseline endpoint | 1d | Step 0 result |
| Step 5 | Eval runner baseline mode + tests | 1d | 4 |
| Step 6 | Comparison run + comparison.json schema | 0.3d | 5 |
| Step 7 | README update | 0.4d | 6 |
| **Total** | | **~9 days** | |

Buffer: ~1 day for prompt iteration if either LLM06 or LLM02 needs
significant catalog-`exemplar_test` rework. S2 needed 0.5 day on
LLM01, two new risks plausibly need ~1 day total.

Realistic ETA: **9–11 days**, may slide into Week 6 prefix.

---

## What unblocks the Week-6 check-in

| Criterion | After S3 | Status |
|---|---|---|
| End-to-end pipeline | ✓ on 6 samples | Met |
| Baseline endpoint live | ✓ | Met |
| Baseline-vs-AgentTest comparison | ✓ (6 pairs each, both modes) | Met |
| ≥ 3 OWASP risks | ✓ (LLM01 + LLM06 + LLM02) | Met |
| ≥ 15 test cases | ✗ (have 6) | **Slip to S4**, README is honest about this |
| Recall/precision numbers | ✓ in both modes | Met |

The slip on case count is deliberate (per § "Why breadth over
depth") and disclosed. S4 expands each risk to ~5 samples,
adds Agentic_Multi_Tenant, and runs the first ablation rows.

---

## Out of scope for S3 (deferred to S4+)

- Agentic_Multi_Tenant risk (S4)
- Pattern library + sentence-transformers + retrieval index (S4
  ablation)
- Sample expansion to ≥ 15 (S4)
- Full ablation matrix (S4)
- SSE progress events (S4 — replaces `logger.info` with async generator)
- Skill packaging (S5)
- Final README polish (S5)
- SLF4J shim (deferred indefinitely; LLM02 sample uses JUL directly,
  realism trade documented in the LLM02 sample comments)
- Resilience4j retry/CB risk (deferred indefinitely)

---

## Pre-S3 cleanups (do these first)

S2 left a few items the code-reviewer flagged. Roll into a single
small commit before S3 Step 0:

1. **`engine/src/agenttest/aggregator/emit.py:64-75`** — `_dedup_imports`
   docstring claims "log if the same name appears twice" but no
   `logger.info` call exists. Add the log OR strike the docstring
   claim.

2. **`engine/src/agenttest/aggregator/emit.py:36-39`** — import-stripping
   regex applies anywhere in the file (re.MULTILINE). Scope the
   regex to source-text region from start to first `@Test` /
   method declaration so a string literal `"import x;"` inside a
   method body isn't hoisted out.

3. **`README.md`** — top-level status says "Sprint S1 (Week 4)". Bump
   to "S2 complete; S3 in progress" so any visitor of the GitHub
   repo doesn't see a stale status during S3 work.

4. **`docs/plan/architecture.md`** — add a one-paragraph "S2
   retrospective" subsection covering the two prompt-iteration
   findings: (a) `target_class_fqn` must be threaded explicitly;
   (b) sample `sanitize()` coverage must match OWASP
   `invariant_to_assert` payload list. Future S3+ samples must
   validate these.

5. **`engine/tests/test_eval_runner.py:53`** — `# type: ignore[arg-type]`
   without inline justification. Add a one-line comment.

Total: ~half a day. **Do these BEFORE Step 0** so the repo state at
S3-start is clean.

---

## What "S3 done" means

Run from a fresh clone (this is the literal grader command):

```bash
git clone https://github.com/c1375/AgentTest.git
cd AgentTest/engine
pip install -e ".[dev]"
python eval/runner-helper/setup.py
echo 'ANTHROPIC_API_KEY=sk-ant-...' > .env
py -3.13 eval/compare.py
```

— produces `engine/eval/results/comparison-<ts>.json` and prints the
headline:

```
Comparison complete: 6 pairs each
  Pipeline: Recall@class=X% | Precision=Y%
  Baseline: Recall@class=A% | Precision=B%
  Delta:    +Z pp recall
```

If the delta is positive (any margin), the project's central claim is
empirically supported and the Week-6 narrative writes itself. If the
delta is zero or negative — that **is the project's honest finding**,
not a failure to ship: the methodology is demonstrable, the numbers
are real, and "the simpler tool was already enough" is itself a
respectable course-project conclusion. We anchor on honesty regardless
of the number's sign.

The success thresholds in `docs/project_plan.md` § 5 (Recall ≥ 60%,
beats baseline by ≥ 15 pp, etc.) are the **S5 final-deliverable**
bar — not the Week-6 check-in bar. S3 just needs the comparison to
exist and be defensible.
