# CLAUDE.md — AgentTest

Per-project instructions for Claude Code working in this repository.

**AgentTest** is a Generative AI course final project (Week 4–8) packaged as
a **Claude Code skill**. Goal: when a Spring AI / LangChain4j / MCP developer
opens their Java project in Claude Code and types `/agenttest <file>`, our
skill produces JUnit 5 tests that are better than what vanilla Claude writes —
specifically by anchoring tests to **OWASP LLM Top 10 risks** and writing
**invariant tests, not behavior-match tests**.

## Architecture history (read before non-trivial decisions)

The repo has been through a major pivot. The journey is the project:

| Phase | Plan doc | What was built |
|---|---|---|
| S1–S3 (engine era) | `docs/plan/sprint-2.md` + `sprint-3.md` | FastAPI engine with analyzer / retrieval / generator / validator pipeline + synthetic injection eval harness |
| S4 v2 (current) | `docs/plan/sprint-4.md` | **Pivot to skill-native architecture**. Engine deleted. Skill = `claude-skill/agenttest/` instructs the user's existing Claude Code session, no separate LLM service |

The pivot rationale (why engine was removed) lives in `docs/plan/sprint-4.md`
§ "Why pivot". The course-facing rationale lives in `docs/project_plan.md` /
`docs/project_plan.zh.md`.

The course assignment requirements live in `docs/ASSIGNMENT.md` and **bind
every design decision**. When in doubt, defer to `docs/ASSIGNMENT.md`.

## Quick Reference

| Component | Location | Purpose |
|---|---|---|
| Skill source | `claude-skill/agenttest/` | The deliverable (SKILL.md + rules/) |
| Install script | `bin/install-skill.ps1` | Copies skill to `~/.claude/skills/agenttest/` |
| Phase 2 eval | `experiments/chainworkflow/` | Real-world eval artifacts on `ChainWorkflow.java` |
| Real-world target | `E:\桌面\Generative AI\spring-ai-examples` | Spring AI Examples repo, pinned `2a6088d` (cloned alongside) |

## CRITICAL RULES — YOU MUST FOLLOW

1. **Skill-native, NOT external service.** `SKILL.md` instructs the user's
   existing Claude Code session — it does NOT call out to a separate Python
   engine or LLM API. No `ANTHROPIC_API_KEY` needed for the skill path.
   The skill's value-add is **OWASP grounding + agent-pattern recognition +
   invariant-test discipline**, not a fancier LLM call.

2. **Generated tests are advisory, not authoritative.** A human must review
   tests before they land in any real project's `src/test/java`. The README,
   `SKILL.md`, and any user-facing surface must say so explicitly. This is
   a course assignment requirement (`docs/ASSIGNMENT.md` "where a human
   should stay involved") AND engineering common sense — an LLM-written
   test that asserts the wrong invariant locks bad behavior in.

3. **OWASP is the source of truth for risk taxonomy.** Anchor risk
   categories to OWASP Top 10 for LLM Applications / OWASP LLMSVS / OWASP
   Top 10 for Agentic AI. Don't invent risk categories. Cite specific risk
   IDs (LLM01, LLM02, LLM06, etc.) in skill rules.

4. **Invariant tests, not behavior-match tests.** Tests should fail on
   buggy code AND pass on correct code. A test that asserts current
   behavior won't catch bugs (the buggy code IS the current behavior).
   The skill MUST teach Claude to assert what SHOULD be true, not what
   IS true. This is the project's #1 differentiator vs vanilla Claude.

5. **Skill structure follows clear-solutions/unit-tests-skills convention**:
   `SKILL.md` (5-step orchestrator) + `rules/` directory of modular markdown
   rules grouped by `general/` / `owasp/` / `patterns/` / `java/unit/` /
   `post-generation/`. Don't put everything in one file. Reference:
   <https://github.com/clear-solutions/unit-tests-skills>.

## Workflow

- **For code review**: invoke the `code-reviewer` sub-agent (after
  non-trivial changes, before commits)
- **For status check**: `/status`
- **For end-of-session sync**: `/debrief`
- **For locking a design decision**: `/decision`

This is a single-developer course project. Don't impose multi-agent TDD
pipelines.

## Repo Layout (post-pivot)

```
AgentTest/
├── CLAUDE.md                            # this file
├── README.md                            # user-facing (rewrite due in Phase 4)
├── .gitignore
├── docs/
│   ├── ASSIGNMENT.md                    # course requirements (source of truth)
│   ├── project_plan.md / .zh.md         # course deliverable doc (pre-pivot — needs update)
│   └── plan/
│       ├── sprint-2.md                  # historical (engine era, kept as narrative)
│       ├── sprint-3.md                  # historical (engine era, kept as narrative)
│       └── sprint-4.md                  # CURRENT plan (pivot to skill)
├── claude-skill/
│   └── agenttest/
│       ├── SKILL.md                     # 5-step orchestrator
│       └── rules/
│           ├── general/                 # cross-language testing principles
│           ├── owasp/                   # LLM01 / LLM02 / LLM06 invariants + payloads
│           ├── patterns/                # agent pattern recognition rules
│           ├── java/unit/               # JUnit 5 + Mockito + AssertJ specifics
│           └── post-generation/         # mvn test-compile + mvn test verification
├── experiments/
│   └── chainworkflow/                   # Phase 2 eval (V_clean, test outputs, results.md)
├── bin/
│   └── install-skill.ps1                # install skill to ~/.claude/skills/
└── .claude/                             # Claude Code workflow config
    ├── agents/code-reviewer.md
    ├── commands/{debrief,decision,status}.md
    └── hooks/{guard-dangerous-bash,post-edit-reminders}.sh
```

## Architecture Source of Truth

**The current architectural decision record is `docs/plan/sprint-4.md`.**
When `sprint-4.md` and `docs/project_plan.md` disagree, `sprint-4.md` wins
(project_plan.md is pre-pivot and pending update). When `docs/ASSIGNMENT.md`
and any other doc disagree, `docs/ASSIGNMENT.md` wins.

There is no separate `ARCHITECTURE.md` and there will not be one.

## When the User Says…

| User says | You should… |
|---|---|
| "skill" | The Claude Code skill at `claude-skill/agenttest/`. `SKILL.md` is the entry point; `rules/` holds the modular instructions. |
| "engine" | Refer to historical context — the pre-pivot engine has been removed. Git history before the cleanup commit has the code if archeology is needed. |
| "ChainWorkflow" / "spring-ai-examples" | The Phase 2 eval target. Real OSS file with unfixed OWASP LLM01 vulnerability at line 121. Located at `E:\桌面\Generative AI\spring-ai-examples\agentic-patterns\chain-workflow\src\main\java\com\example\agentic\ChainWorkflow.java`, pinned to commit `2a6088d`. |
| "OWASP" | Without further context, OWASP Top 10 for LLM Applications + OWASP LLMSVS + OWASP Top 10 for Agentic AI. Cite the specific risk ID (LLM01, LLM02, LLM06, etc.). |
| "MyKefi" | The user's parallel Java project at `D:\MyKefi\MyKefi-App\MyKefi-AI-Platform`. AgentTest does NOT depend on MyKefi. Do not read MyKefi files. |
| "test gen" | The skill (`/agenttest <file>` workflow), NOT a Python pipeline. |
| "下一步" / "next" | Refer to `docs/plan/sprint-4.md` § "Implementation phases". |
