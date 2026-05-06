# AgentTest

Agent-aware JUnit test generator for Java AI agent code (Spring AI /
LangChain4j / MCP). Final project for a Generative AI course.

> **Status (Week 6):** S3 complete. Pipeline + single-prompt baseline
> both live; eval harness compares them via
> [`engine/eval/compare.py`](engine/eval/compare.py). On the
> [2026-05-06 comparison run](engine/eval/results/comparison-2026-05-06T19-26-58.json)
> (6 hand-curated samples covering LLM01 prompt injection, LLM02
> sensitive-data disclosure, LLM06 excessive agency / tool-description
> mismatch), both pipeline and baseline catch **4 of 6 injected risks
> on the full set (66.7%)** with 100% precision on measured pairs. The
> differentiator is **failure mode**, not headline recall:
>
> - **Pipeline** drops 2 sites at the validator gate (output failed
>   compile or run-on-clean) → silent skip, the user sees no broken
>   tests.
> - **Baseline** ships 2 tests with wrong invariants that FAIL on the
>   clean code → silent false-alarm in CI, the user pays a noise cost
>   on every run.
>
> S4 (Week 7) expands the test set to 30–50 samples and runs the full
> ablation matrix (analyzer-only / + OWASP retrieval / + agent-pattern
> retrieval / full system) so this differentiator is tested at scale.
> See [`docs/plan/sprint-3.md`](docs/plan/sprint-3.md) § "Step 6" for
> the comparison rationale and per-sample table.

## What this is

Given a Java class implementing AI-agent logic, AgentTest produces a JUnit 5
test class targeting agent-specific invariants that general Java test
generators miss — prompt injection in template assembly, tool description /
implementation mismatch, sensitive-data leakage, multi-tenant boundary
violations, retry / circuit-breaker misconfigurations. OWASP-anchored risks
are the subset used as objective evaluation ground truth (see
[`docs/project_plan.md`](docs/project_plan.md) § 1, § 5).

**Generated tests are advisory only — a human must review every test
before it lands.** No test is ever auto-merged.

## Plan and assignment

- [`docs/project_plan.md`](docs/project_plan.md) — full design rationale (English)
- [`docs/project_plan.zh.md`](docs/project_plan.zh.md) — same plan (Chinese)
- [`docs/ASSIGNMENT.md`](docs/ASSIGNMENT.md) — course assignment requirements

## Repo layout

- `engine/` — FastAPI engine + analysis pipeline (Python 3.11, async)
- `docs/` — project plan, assignment, ongoing planning notes
- `.claude/` — Claude Code workflow config (this repo is co-developed with Claude Code)

## Setup (Week-6 preview — grader-facing CLI walkthrough lands in S4)

```bash
cd engine
pip install -e ".[dev]"
pytest -m "not integration"             # 92 unit tests (no LLM, no JDK)
pytest                                   # +8 integration (needs JDK 17+ on PATH)
```

Real generation requires `ANTHROPIC_API_KEY` in `.env` (copy from
`.env.example`). With a key set, reproduce the Week-6 comparison:

```bash
py -3.13 eval/runner-helper/setup.py     # one-time JDK toolchain bootstrap
py -3.13 eval/compare.py                 # pipeline + baseline + delta JSON
```

**Cost.** One full comparison run costs **~$0.60** in Anthropic credits
on the 6-sample test set (one Sonnet call per pipeline (site, risk) pair
+ one Sonnet call per baseline sample). A full S3-iteration cycle
(prompt smoke tests + tweaks + final comparison) ran ~$5–10 total. A
grader running `eval/compare.py` once: ≤ $1.
