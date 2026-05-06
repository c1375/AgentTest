# Sprint 4 Plan

S4 closes the **Week-7 deliverable**: scaling AgentTest's evaluation
from a 6-sample preview into a real 4-row ablation, plus polish for
the grader-facing surface. After S3 we have 3 OWASP risks measured
end-to-end on 6 samples with a working baseline endpoint, and the S3
comparison surfaced 2 pipeline failure cases on `WeatherTool` and
`EmailDraftingAssembler` — generator hallucinated inner-class
references and wrong types on the target class itself.

> Source-of-truth scoping line, copied from `docs/project_plan.md` § 8:
> *"Test set to 30–50 cases. Full ablation matrix. Second-pass on
> weakest risk categories. CLI polish. README first draft (clone →
> run on one example). Pre-recorded demo clip captured."*

This plan deviates from § 8 on three points:

1. **Sample count** lands at 15, not 30–50. project_plan §5 anticipated
   this with the explicit out: *"if sample synthesis runs slow we
   accept landing at the lower end of the range (~15 samples)."*
   Authoring real Spring-AI / LangChain4j / MCP samples that satisfy
   their injection regex is 1–2 hours each, not 30 minutes; 24 new
   samples would consume the entire sprint and leave no time for the
   ablation matrix or polish.
2. **Ablation matrix** is **4 rows, not 5** (no agent-pattern retrieval
   row). See "Why pattern retrieval defers to S5" below.
3. **README "first draft"** was already shipped in S3 Step 7. S4
   polishes (adds ablation table + worked example), not first-drafts.

---

## Why this scope (S4 theory of change)

S3 proved the methodology generalizes: 3 risks, 6 samples, baseline
comparison. The Week-6 finding was that pipeline and baseline both
hit 4/6 catch on the full set, with **mutually-exclusive failure
modes**:

- Pipeline: 2 sites validator-dropped (output failed compile or
  run-on-clean — generator hallucinated symbols not present on the
  target class).
- Baseline: 2 sites shipped wrong invariants (FAIL on clean code).

S4's theory of change has two parts:

1. **Scale exposes the differentiator.** With N=6 the headline is
   "tied at 66.7%" — visually unimpressive even though the
   failure-mode signal is real. With N=15 we get a 5×-larger
   measurement of each mode's ship-bad-tests rate. Pipeline ≈ 0%
   by validator-gate construction; baseline was 33% on S3. Even
   with N=15, that 33pp delta is a clear statistical signal.

2. **Anti-hallucination prompt constraint should reduce pipeline's
   validator-drop rate.** The S3 drops were "generator hallucinated
   `WeatherTool.StubWeatherClient`" and "wrong types in
   `EmailDraftingAssembler`" — the generator referenced symbols
   not visible in the target source. Tightening the generator
   system prompt to explicitly disallow this is a one-line edit
   that gets measured naturally by the S4 ablation run; no extra
   experiment needed.

The 4-row ablation matrix tests whether each component
(analyzer, OWASP catalog retrieval, validator gate) **measurably
helps** — per assignment requirement to drop components that
don't.

---

## Why pattern retrieval defers to S5

The first draft of this plan included a 5th ablation row for
agent-pattern retrieval (1–3 similar Java class examples retrieved
per (site, risk) pair via sentence-transformers embedding). On
adversarial review this was cut for two reasons:

1. **Pattern retrieval is the wrong fix for the observed pipeline
   failures.** The S3 drops were "generator referenced
   `StubWeatherClient`" — i.e., **invented inner classes that don't
   exist on the target class**. Pattern retrieval provides examples
   of *similar but different* classes; it doesn't constrain the
   generator to the target's actual API. The right fix is a
   tighter system prompt + the analyzer's existing site source
   (already passed in). This is decision **#5 below**.
2. **Engineering cost vs. proven value is poorly balanced for
   S4.** Library bootstrap (30 patterns across 3 stacks) +
   embedding pipeline + retrieval module + wiring + tests ≈ 3 days
   — half the sprint. ASSIGNMENT.md says "drop RAG sources that
   don't measurably help" — but the assignment wants us to *test*
   sources we ship, not ship sources we suspect won't help. With
   the prompt-tightening alternative cheaper and more directly
   targeted at the observed failure mode, S4 ships without
   pattern retrieval.

S5 (Week 8) revisits pattern retrieval if the S4 ablation shows
OWASP-only RAG is insufficient, OR if the assignment grader
specifically asks about the second retrieval source. Until then
it's a documented deferral, not a forgotten one.

---

## Locked decisions

### 1. Sample count = 15 (5 per risk × 3 risks)

9 new samples join the existing 6: 3 new LLM01 + 3 new LLM02 +
3 new LLM06. Per-risk counts give us:
- Per-risk recall variance band: with N=5 per risk, sample
  resolution is 20pp per risk — coarse but lets us spot a
  catastrophic per-risk regression.
- Cross-risk consistency: same prompt against three invariant
  shapes, measured at the same N, lets us see whether one risk
  underperforms the other two.

Authoring estimate: 1.5h per sample × 9 = ~13h = 1.7d. project_plan
§5's explicit floor.

### 2. Agentic_Multi_Tenant (4th risk) deferred to S5 with locked language

Reason: multi-tenant samples need session-context plumbing
(`TenantContext` or similar) that no canonical Spring AI pattern
provides — we'd be inventing one to test against, which is
circular.

The lightning slides + README ablation section will state this
verbatim:

> *"S4 covers LLM01 / LLM02 / LLM06 — the three risks that map to
> existing Spring AI / LangChain4j / MCP idioms with no extra
> framework plumbing. Multi-tenant boundary violations require
> per-codebase session-context plumbing (TenantContext etc.); we
> defer this to S5 to avoid testing AgentTest against a pattern
> we invented ourselves."*

This is a deliberate scope choice, not an oversight. Step 8
(README polish) lifts this language verbatim into the ablation
section.

### 3. Ablation matrix = 4 rows on the full 15-sample set

| # | Mode (`run_eval(mode=...)`) | Analyzer | OWASP retrieval | Validator gate |
|---|---|---|---|---|
| 1 | `baseline`                | ✗ | ✗ | ✗ |
| 2 | `pipeline-analyzer-only`  | ✓ | ✗ | **✗** |
| 3 | `pipeline-no-retrieval`   | ✓ | ✗ | ✓ |
| 4 | `pipeline-full`           | ✓ | ✓ | ✓ |

Each adjacent-row delta isolates exactly one added component:

- **1 → 2**: does the analyzer + risk-targeted prompt help over the
  single-prompt baseline?
- **2 → 3**: does the validator gate help on top of the analyzer?
- **3 → 4**: does OWASP catalog retrieval help on top of the gated
  analyzer?

Why this differs from `docs/project_plan.md` §5: the original
matrix had pattern retrieval as a 4th independent dimension. With
pattern retrieval deferred to S5 (decision #2 above), "Analyzer +
OWASP retrieval" and "Full system" would be identical rows. Moving
the validator gate from "always-on" (project_plan §5's implicit
assumption) to "the dimension exposed by row 2 vs row 3" keeps the
matrix at 4 distinct rows AND lets the validator's marginal value
be measured directly — which is exactly what the failure-mode
narrative from S3 needs.

Eval reports per-row recall, precision, and ship-bad-tests rate
(decision #4). Ship-bad-tests is what makes row 2 (no gate)
informative: it should look better than baseline on ship-bad-tests
because the analyzer narrows the test target, but worse than rows
3–4 because uncompilable / clean-failing tests aren't being
filtered out.

### 4. Headline metrics = recall + ship-bad-tests rate (derived)

S3 found that recall alone undersells the pipeline's failure-mode
advantage. S4 reports both:

- **Recall@class** (per project_plan §5)
- **Ship-bad-tests rate** = % of (sample, risk) pairs where the
  mode emits a test that FAILS on clean code

For pipeline modes, ship-bad-tests is **derived** from existing
emission stats — `refused_sites` already records what the
validator dropped. We thread one new field through: the
**drop-reason category** (`compile_fail` / `clean_fail` / `other`)
on each refusal, so the eval can count "would-have-shipped-broken"
rates without a separate validator-bypass mode. This is cheaper
than the bypass-mode alternative considered in the first draft
(~1h vs ~0.5d) and uses real validator outcomes rather than
hypotheticals.

### 5. Generator prompt: explicit anti-hallucination constraint

`engine/src/agenttest/generator/prompt.py` system prompt gets one
new bullet:

> *"Only reference Java symbols (classes, methods, fields) that
> appear verbatim in the target source. Do not invent inner
> classes, fields, or methods on the target class. If a needed
> symbol is missing, refuse with `refused: true` rather than
> hallucinating it."*

This is a free code edit. The S4 ablation run measures whether it
helped; if WeatherTool / EmailDraftingAssembler-style failures
disappear, we keep it. If it has no effect, we keep it anyway —
it can't hurt, and the assignment likes constraints that promote
honesty.

### 6. CLI polish = Windows-first, single worked example

Dev environment is Windows; we ship only `bin/setup.ps1` (not a
sibling `setup.sh`) since shipping an untested bash script is
worse than shipping documentation. README "Setup" lists the
PowerShell commands and gives the equivalent Unix commands inline
as documentation, with a note that the Unix path is unverified
on this dev machine.

One worked example (RestaurantPromptAssembler input → CLI command
→ output JUnit test class) lands inline in README per
project_plan §8.

### 7. Demo clip — pre-recorded, single take, 30–60s

Per project_plan §8: CLI run → generated test class shown → JVM
compile + run on clean (PASS) and buggy (FAIL). Single take,
no editing. Stored as `docs/demo.mp4` or linked to YouTube
unlisted (size).

---

## Implementation steps

### Step 1 — Sample expansion (9 new samples)

`engine/eval/samples/spring_ai/<sample>.java` + `<sample>.meta.yaml`
for 9 new samples:
- 3 new LLM01 (joining the existing 2)
- 3 new LLM02 (joining the existing 2)
- 3 new LLM06 (joining the existing 2)

Each meta.yaml lists `applicable_injections` from the existing 3
injection scripts. Samples synthesized from public OSS Spring AI
/ LangChain4j / MCP examples — no proprietary code.

Tests: existing eval harness validates meta.yaml format; the
preflight check from Step 1.5 catches injection-regex mismatches.

### Step 1.5 — Sample preflight check

`engine/eval/preflight.py` — for each sample × each
`applicable_injection` listed in meta.yaml, run the injection's
`apply()` on the sample's clean Java and assert the output is
**non-trivially different** from the input (not the empty diff
case where the regex didn't match).

Run as a pytest in `tests/test_eval_preflight.py` so CI catches
regressions, AND as a sanity-check before any ablation run.

A bad sample (injection doesn't actually mutate the source)
silently produces `pipeline_error` rows in the eval and pollutes
the headline numbers. S3 had one near-miss here. This step
turns silent failure into a test-time hard error.

Tests: `engine/tests/test_eval_preflight.py` — checks each sample
on each applicable injection, fails the test if any (sample,
injection) pair produces a no-op diff.

### Step 2 — Generator prompt anti-hallucination constraint

`engine/src/agenttest/generator/prompt.py` — append the
"only reference symbols visible in the target source" bullet
(see decision #5).

Tests: existing generator-prompt assertions (the lock-in tests
in `test_generator_synthesize.py` if any) updated to include the
new bullet's substring.

### Step 3 — Ablation harness (4-row mode routing)

`engine/eval/runner.py` extended with a `--mode` argument
accepting:
- `pipeline-full` (default; analyzer + OWASP retrieval +
  validator gate)
- `pipeline-no-retrieval` (analyzer + raw site, no OWASP
  retrieval, validator gate still applied)
- `pipeline-analyzer-only` (analyzer + raw site, no validator
  gate — yes, this row tests the gate's value)
- `baseline`

Each emits to `run-<mode>-<ts>.json`.

`engine/eval/ablation.py` (new, sibling of `compare.py`):
orchestrates all 4 modes back-to-back, emits one
`ablation-<ts>.json` with per-row stats and per-(row, row+1)
deltas.

Tests: extend `test_eval_runner.py` with mode-routing tests
(no-LLM, monkey-patched).

### Step 4 — Ship-bad-tests metric + drop-reason threading

Three small changes:

1. `engine/src/agenttest/contracts.py` — extend `RefusedSite` (or
   the analogous tuple-shape) with a `drop_category` field:
   `Literal["compile_fail", "clean_fail", "model_refused", "other"]`.
2. `engine/src/agenttest/pipeline.py` — when validator drops a
   test, classify the drop reason and stamp it on the refused-site
   tuple before appending.
3. `engine/eval/results.py` — add `ship_bad_tests_rate` to
   `SummaryStats`. Definition: % of (sample, risk) pairs where
   the mode emits a test that FAILS on clean code.
   - Baseline: counted directly from `clean_outcome == "FAIL"`.
   - Pipeline modes with validator gate: counted from refused-sites
     with `drop_category in ("compile_fail", "clean_fail")` —
     these would have shipped without the gate.
   - Pipeline mode without validator gate
     (`pipeline-analyzer-only`): direct count.

Tests: extend `test_eval_runner.py` summary-math tests.

### Step 5 — Real ablation run + analysis

`py -3.13 eval/ablation.py` — full 4-row × 15-sample run.

Cost budget per run: 4 rows × 15 × 1.3 risks × $0.07 + baseline
$3 ≈ $8.50. **S4 cumulative budget cap: $40** (allows ~3
iterations + headroom for debugging).

Output: `engine/eval/results/ablation-<ts>.json`.

**Component-drop rule per assignment:** if a row's recall
improvement over the row above is not "meaningful" (qualitative,
per ASSIGNMENT.md), the row is documented in the README as
"tested, no measurable lift; dropped from the deliverable." We
don't auto-drop in code — the row stays runnable for grader
verification.

### Step 6 — CLI polish (Windows-first)

`bin/setup.ps1` — bootstrap `.env` from `.env.example` (prompt
for `ANTHROPIC_API_KEY` interactively if not set), install deps,
run `eval/runner-helper/setup.py`, run
`pytest -m "not integration" -q` as a smoke test.

README "Setup" section rewritten as a clone-to-first-run
walkthrough using the PS script. The Unix-equivalent commands
are listed inline as documentation only, with a "(not tested
on this dev machine)" note.

### Step 7 — Demo clip

Pre-recorded ~30–60s screencast: CLI run on
`RestaurantPromptAssembler` → generated test class shown → JVM
compile + run on clean (PASS) and buggy (FAIL). Stored as
`docs/demo.mp4` (committed if size permits, ~5MB max) or linked
to YouTube unlisted.

### Step 8 — README polish (ablation table + worked example + locked language)

- Status block updated to "S4 complete; Week-7 evidence linked"
- Add ablation table: 4 rows × Recall@class / Precision /
  Ship-bad-tests / Cost per row
- Add the worked example (RestaurantPromptAssembler input →
  CLI command → output JUnit test class) inline as code blocks
- Lift decision #2's multi-tenant defer language verbatim into
  the ablation section
- Link to `engine/eval/results/ablation-<ts>.json` (force-add
  the canonical run via the same gitignore exception pattern
  S3 used)

---

## Sequenced timeline (~5 days)

| Step | What | Estimate | Depends on |
|---|---|---|---|
| Step 1 | 9 new samples + meta.yaml | 1.7d | — |
| Step 1.5 | Sample preflight check (ship-blocker) | 0.3d | Step 1 |
| Step 2 | Generator anti-hallucination prompt | 0.1d | — |
| Step 3 | Ablation harness (4-row routing) | 0.7d | — |
| Step 4 | Ship-bad-tests metric + drop-reason threading | 0.6d | Step 3 |
| Step 5 | Real ablation run + analysis | 0.5d | Steps 1.5, 4 |
| Step 6 | CLI polish (PS-only) | 0.3d | — |
| Step 7 | Demo clip | 0.2d | Step 6 |
| Step 8 | README polish + locked multi-tenant text | 0.5d | Step 5 |
| **Total** | | **~4.9d** | |

Ablation row total: **4 rows × 15 samples** = 60 (sample, mode)
pairs per ablation run, ~$8.50 each. **S4 LLM budget cap: $40
cumulative.** S5 (Week 8) is final polish + lightning
presentation — no new generator work expected.
