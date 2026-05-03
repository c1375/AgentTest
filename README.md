# AgentTest

Security-aware JUnit test generator for Java AI agent code (Spring AI /
LangChain4j / MCP). Final project for a Generative AI course.

> **Status:** Sprint S1 (Week 4) — scaffold in place; analyzer / retrieval /
> generator / validator / evaluator stages are being built next. The polished
> README, runnable example, and evaluation results land by Week 8.

## What this is

Given a Java class implementing AI-agent logic, AgentTest produces a JUnit 5
test class that targets OWASP-aligned risks for LLM agents — prompt injection
in template assembly, tool description / implementation mismatch, sensitive-
data leakage, multi-tenant boundary violations, retry / circuit-breaker
misconfigurations.

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
