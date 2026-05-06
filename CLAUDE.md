# CLAUDE.md — AgentTest

Per-project instructions for Claude Code working in this repository.

**AgentTest** is a Generative AI course final project (Week 4–8). It is an
**agent-aware unit test generator for Java AI agent code** — Spring AI,
LangChain4j, MCP server implementations. Input = a Java class implementing
an agent pattern (prompt assembler, tool handler, MCP server, etc.). Output
= a JUnit 5 test suite covering three classes of agent invariants:

1. **Safety** (OWASP-anchored): prompt injection, sensitive-data leakage,
   multi-tenant boundary, excessive tool agency.
2. **Agent-pattern correctness**: tool schema vs. implementation conformance,
   prompt-template stability, RAG-context handling.
3. **Reliability**: retry / circuit-breaker boundaries, idempotency under
   transient failure.

OWASP is the **eval ground truth** — the synthetic-injection harness only
scores risks in category (1), keeping the primary metric model-as-judge-
free. Categories (2) and (3) ride on the same pipeline but are not part of
the headline recall / precision number. See `docs/project_plan.md` § 1, § 5.

Generated test class files are named `<TargetClass>AgentGenTest.java`. The
baseline synthesizer's system prompt deliberately retains the narrower
"security-focused Java test engineer" role — it simulates a developer
using Claude alone with a security focus and is the fair-comparison
baseline, not the project's positioning.

The full design rationale lives in `docs/project_plan.md` (English) /
`docs/project_plan.zh.md` (Chinese) — read it before making non-trivial decisions.

The course assignment requirements live in `docs/ASSIGNMENT.md` and **bind every
design decision**. When in doubt, defer to `docs/ASSIGNMENT.md`.

## Quick Reference

| | Engine (`engine/`) |
|-|-----------|
| Stack | FastAPI + Python 3.11 |
| Port | `8000` |
| Run (dev) | `cd engine && uvicorn agenttest.main:app --reload --port 8000` |
| Run (docker) | `docker build -t agenttest engine/ && docker run -p 8000:8000 agenttest` |
| Test | `cd engine && pytest` |
| Install | `cd engine && pip install -e ".[dev]"` |

There is no UI. Surfaces are: a CLI (for evaluation), the FastAPI server
(for the Claude Code skill), and (later) a packaged skill / MCP tool.

## CRITICAL RULES — YOU MUST FOLLOW

1. **No real LLM calls in unit tests.** `tests/test_agents.py` validates
   factory wiring without making API calls. Anything that needs Anthropic
   should use a mock or be marked as an integration test (explicit opt-in
   via `@pytest.mark.integration`).

2. **Secrets via `.env` only.** Never hard-code an API key. The default
   `anthropic_api_key` in `config.py` is the placeholder
   `sk-placeholder-for-startup` — that is intentional, mirroring MyKefi's
   pattern, so the app boots without real keys.

3. **`agents.yaml` is the per-role model contract.** When adding a new LLM
   role: (1) add an entry in `engine/configs/agents.yaml`, (2) add the value
   to the `AgentRole` enum in `engine/src/agenttest/agents/role.py`. Both.
   Don't add a role only in code — the factory iterates `AgentRole` and
   looks each one up in YAML.

4. **Generated tests are advisory, not authoritative.** AgentTest synthesizes
   JUnit tests; **a human must review them before they land in any real
   project's `src/test/java`**. The README, the lightning presentation, and
   any user-facing surface must say so explicitly. This is a course
   assignment requirement (`docs/ASSIGNMENT.md` "where a human should stay
   involved") and it is also engineering common sense: an LLM-written test
   that asserts the wrong invariant locks bad behavior in.

5. **OWASP is the source of truth for risk taxonomy.** When defining or
   refining a risk category the system targets, anchor it to OWASP Top 10
   for LLM Applications / OWASP LLMSVS / OWASP Top 10 for Agentic AI.
   Don't invent risk categories from scratch — cite the OWASP entry in
   prompts and in eval cases.

6. **Eval ground truth is synthetic injection.** The eval harness takes a
   library of clean Java agent code samples, injects a known OWASP-aligned
   risk pattern, runs AgentTest on the now-buggy sample, and checks
   whether the synthesized tests fail on the buggy version (good) and
   pass on the clean version (good). Recall / precision are measured
   against this objective ground truth — **no model-as-judge for the
   primary metric**.

## Workflow

This is a single-developer course project. Don't impose multi-agent TDD
pipelines.

- **For backend code**: invoke the `python-backend-dev` sub-agent
- **For code review**: invoke the `code-reviewer` sub-agent (after
  non-trivial changes, before commits)
- **For status check**: `/status`
- **For end-of-session sync**: `/debrief`
- **For locking a design decision**: `/decision`

Tests are nice-to-have, not required for every change. Critical-path code
(factory wiring, Java AST analyzer, prompt assembly, mutation harness,
schema validators) gets tests; one-off scripts don't.

## Repo Layout

```
AgentTest/
├── CLAUDE.md                             # this file (Claude Code project rules)
├── .env.example
├── docs/
│   ├── ASSIGNMENT.md                     # course requirements (source of truth)
│   └── project_plan.md / project_plan.zh.md  # the course deliverable
├── engine/                               # FastAPI server + analysis pipeline
│   ├── pyproject.toml
│   ├── Dockerfile
│   ├── src/agenttest/
│   │   ├── main.py                       # FastAPI app + lifespan
│   │   ├── config.py                     # pydantic-settings
│   │   ├── http/                         # routes, SSE
│   │   ├── agents/                       # per-role Claude clients
│   │   └── adapters/                     # provider registry (Anthropic etc.)
│   │   # to be added during implementation:
│   │   # ├── analyzer/                   # Java AST + risk identification
│   │   # ├── retrieval/                  # OWASP catalog + agent patterns
│   │   # ├── generator/                  # JUnit test synthesis
│   │   # └── evaluator/                  # mutation-injection harness
│   ├── tests/
│   ├── eval/                             # eval harness (added during impl)
│   └── configs/
│       └── agents.yaml                   # per-role model config
└── .claude/                              # Claude Code workflow config
```

## Architecture Source of Truth

**The only architecture document that matters is `docs/project_plan.md` (or
`docs/project_plan.zh.md`).** Any architectural change must update it. There is
no separate `ARCHITECTURE.md` and there will not be one — `docs/project_plan.md`
is short enough to be the single source.

When `docs/project_plan.md` and this file disagree, `docs/project_plan.md` wins
(except on the points marked CRITICAL RULES above, which bind regardless).
When `docs/ASSIGNMENT.md` and `docs/project_plan.md` disagree, `docs/ASSIGNMENT.md` wins.

## When the User Says…

| User says | You should… |
|-|-|
| "搭框架" / "scaffold" | Re-read `docs/project_plan.md` § 4 (architecture) before adding files |
| "MyKefi" | The user's parallel Java project at `D:\MyKefi\MyKefi-App\MyKefi-AI-Platform`. AgentTest does NOT depend on MyKefi or run against it as part of evaluation. The user may install the AgentTest skill on their own MyKefi repo for personal use, but that is private and not part of the deliverable. Do not read MyKefi files. |
| "agents" / "agent role" | The Python `AgentRole` enum in `engine/src/agenttest/agents/role.py`, which mirrors `engine/configs/agents.yaml`. Not Spring beans. |
| "OWASP" | Without further context, OWASP Top 10 for LLM Applications + OWASP LLMSVS + OWASP Top 10 for Agentic AI. Cite the specific risk ID (LLM01, LLM03, etc.) when referencing. |
| "test gen" / "the eval" | The synthetic-injection eval harness in `engine/eval/` (built during the project), NOT pytest. |
| "skill" | The Claude Code skill packaged at the end of the project that wraps the `/agenttest` workflow. Today it is unbuilt; reference `docs/project_plan.md` § 8 for the surface plan. |
| "下一步" / "next" | Refer to the sprint sequence in `docs/project_plan.md` § 8. |
