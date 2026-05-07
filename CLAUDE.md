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

| Phase | What was built |
|---|---|
| S1–S3 (engine era) | FastAPI engine with analyzer / retrieval / generator / validator pipeline + synthetic injection eval harness. Engine deleted from git in commit `99df6e0`; recoverable via `git show <pre-99df6e0-commit>:engine/...`. |
| S4 (current) | **Pivot to skill-native architecture**. Skill = `claude-skill/agenttest/` instructs the user's existing Claude Code session, no separate LLM service. N=3 real-world eval committed under `experiments/`. |

The course-facing architecture rationale lives in `docs/project_plan.md` /
`docs/project_plan.zh.md`. Detailed sprint planning + phase tracking
lives in `docs/plan/sprint-{2,3,4}.md` — these are **gitignored**
(internal reference only, not on the public repo) but readable locally
when working in this repo.

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

The `.claude/` workflow tooling (sub-agents and slash commands) is
gitignored — it lives only on the local repo for the developer + AI
assistant. The bullets below apply when working locally where these
files exist; on a fresh public clone they are unavailable.

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
├── README.md                            # user-facing
├── LICENSE                              # Apache 2.0
├── .gitignore
├── docs/
│   ├── ASSIGNMENT.md                    # course requirements (verbatim from Canvas)
│   └── project_plan.md / .zh.md         # design rationale (English / Chinese)
├── claude-skill/
│   └── agenttest/                       # the deliverable
│       ├── SKILL.md                     # 7-step orchestrator
│       └── rules/                       # 12 modular markdown rule files
│           ├── general/                 # cross-language test discipline
│           ├── owasp/                   # LLM01 / LLM02 / LLM06 invariants + payloads
│           ├── patterns/                # chain-workflow / iterative-agent / tool-handler / log-handler
│           ├── java/                    # JUnit 5 + Mockito + AssertJ + ChatClient mocking
│           └── post-generation/         # mvn test-compile + mvn test verification
├── experiments/
│   ├── realworld-results.md             # N=3 aggregate results
│   ├── chainworkflow/                   # Phase 2 anchor (test_skill, test_vanilla, V_clean, smoke-result)
│   ├── orchestratorworkers/             # Phase 2 stretch #1
│   └── evaluatoroptimizer/              # Phase 2 stretch #2
└── bin/
    └── install-skill.ps1                # install skill to ~/.claude/skills/
```

Gitignored (local-only, not on public repo):
- `docs/plan/sprint-{2,3,4}.md` — internal sprint planning
- `.claude/{agents,commands,hooks}/` — workflow tooling (sub-agents + slash commands + edit hooks)

## Architecture Source of Truth

**The current architectural decision record is `docs/project_plan.md`**
(its Chinese mirror at `docs/project_plan.zh.md`). It is the public,
course-facing design doc rewritten in Phase 3 to reflect skill-native
+ N=3 eval results. When `docs/ASSIGNMENT.md` and any other doc
disagree, `docs/ASSIGNMENT.md` wins.

`docs/plan/sprint-{2,3,4}.md` are gitignored internal sprint plans;
when needed for detailed phase planning or pivot-rationale archeology,
read them locally — they are not on the public repo and references
to them in tracked docs were removed.

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
| "下一步" / "next" | Refer to `docs/project_plan.md` § 8 (sprint history) for context, then ask the user for the next concrete step — Phase 2 + Phase 3 tasks 1-2 are DONE; remaining is demo clip (Phase 3 task 3) + S5 answer prep. |
