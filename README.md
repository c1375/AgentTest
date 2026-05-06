# AgentTest

Agent-aware JUnit test generator for Java AI agent code (Spring AI /
LangChain4j / MCP). Final project for a Generative AI course.

> **Status:** S2 complete; S3 in progress. The end-to-end pipeline
> (analyzer → generator → validator → aggregator) measures
> Recall@class = Precision = 100% on 2 LLM01 prompt-injection samples
> (`engine/eval/results/run-2026-05-04T00-39-58.json`). S3 widens to
> 3 OWASP risks (LLM01 + LLM06 + LLM02) and adds the baseline endpoint;
> see [`docs/plan/sprint-3.md`](docs/plan/sprint-3.md). Polished README,
> runnable example, and full evaluation results land by Week 8.

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

## Setup (preview)

A grader-facing CLI and a complete setup walkthrough land in S4 (Week 7).
Today, smoke-checking the engine looks like:

```bash
cd engine
pip install -e ".[dev]"
uvicorn agenttest.main:app --reload --port 8000
# in another terminal:
curl http://localhost:8000/agents
```

Real generation requires `ANTHROPIC_API_KEY` in `.env` (see `.env.example`).
