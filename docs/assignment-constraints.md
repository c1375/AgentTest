# Assignment-derived constraints (AgentTest team's reading)

> **Editorial commentary, not the official assignment.** This file
> records how the AgentTest team reads the official course assignment
> ([`ASSIGNMENT.md`](ASSIGNMENT.md)) — a quick-reference summary of the
> implications that bind every AgentTest design decision. The official
> assignment in `ASSIGNMENT.md` is the source of truth; this file is
> our gloss on it. When this file and `ASSIGNMENT.md` appear to
> disagree, `ASSIGNMENT.md` wins.

---

These are the implications that bind every design decision.

## Scope discipline

- **Narrow workflow** — one user, one workflow. Not a platform.
- **Simplest design that lets evaluation work**. RAG, multi-model, multi-stage
  pipelines must each **earn their place** by demonstrably improving over a
  simpler version. If an ablation shows a component doesn't help, **drop it
  from the deliverable** rather than defending it.

## Evaluation discipline

- **Small but real**. The assignment explicitly says small is fine — what
  matters is that the eval reflects realistic examples, not cherry-picks.
- **Mandatory baseline comparison**. Pick one, justify it, run it.
- **Document what counts as good output** before measuring. Don't define the
  rubric after seeing the numbers.
- **Report failures honestly**. "Where it broke down" is a required README
  section.

## Deliverable discipline

- **Runnable by grader**. README must walk a stranger from clone → working
  example. Test this by reading the README cold.
- **No secrets in repo**. `.env` patterns, key-injection instructions in
  README.
- **Artifact must exist as a real, runnable thing** — app / CLI / skill /
  MCP tool / Codex skill. A notebook alone fails.
- **Lightning presentation is 2–3 minutes**. The pitch must compress to that.
  If the pitch needs more than 3 minutes to land, the scope is too wide.

## Human-in-the-loop framing

- "Where a human should stay involved" is a required section. This is not
  optional. The deliverable must explicitly mark which decisions remain
  human even after the tool runs.

## How AgentTest satisfies each constraint

| Constraint | AgentTest's answer |
|---|---|
| Narrow workflow | "Generate JUnit 5 tests for one Java AI agent file at a time" — single user, single workflow |
| Simplest design | Skill-native (no engine, no RAG, no second LLM call); per-pivot decision documented in [`plan/sprint-4.md`](plan/sprint-4.md) § "Why pivot" |
| Small but real eval | N=3 real OSS files in `spring-ai-examples @ 2a6088d`; honest reporting in [`../experiments/realworld-results.md`](../experiments/realworld-results.md) |
| Mandatory baseline | Vanilla Claude Code session with locked baseline prompt 「帮我给 ChainWorkflow.java 写一个测试」 |
| Document good output before measuring | Catch criterion regex + precision criterion fixed in `plan/sprint-4.md` BEFORE Phase 2 ran |
| Report failures honestly | Limitations + known issues section in README + `realworld-results.md`; V_clean v1→v2 lesson written up rather than hidden |
| Runnable by grader | `git clone` → `bin\install-skill.ps1` → `/agenttest <file>` — README walks the path |
| No secrets in repo | No API keys needed (skill-native); `.env` patterns enforced by `.gitignore` |
| Artifact is a real thing | Claude Code skill at `claude-skill/agenttest/` (SKILL.md + 12 rules) |
| 2–3 min presentation | TBD in S5 (Week 8); will compress to "skill 12-0 vs vanilla on 3 real OSS files, framing not capability" |
| Where a human stays involved | SKILL.md Step 7 explicitly: never write to `src/test/java/` without user confirmation; tests are advisory |
