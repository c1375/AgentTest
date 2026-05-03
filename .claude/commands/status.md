---
description: Show current AgentTest status — git, services, tests, sprint
user_invocable: true
---

Display a concise status overview. Gather ALL of the following, then present as a single summary:

## Data to Collect

1. **Git state**:
   - If `.git` exists: current branch via `git branch --show-current`, uncommitted via `git status --porcelain | head -15`, recent commits via `git log --oneline -5`
   - If `.git` does not exist: report "not initialized — run `git init` if you want version control"

2. **Engine health**:
   - `curl -s -o /dev/null -w "%{http_code}" http://localhost:8000/health` — report HTTP code or "DOWN"
   - If up, also `curl -s http://localhost:8000/agents` and report which roles loaded (just the keys, not the full config)

3. **Test status**:
   - `cd engine && pytest --collect-only -q 2>/dev/null | tail -3` — total test count

4. **Sprint progress** — read `docs/project_plan.md` § 8 for what should be done by Week 6, compare against current state, identify which sprint (S1/S2/S3/S4/S5) we are plausibly in.

## Output Format

```
## AgentTest Status

**Git:** main (clean | 3 uncommitted) — last: abc1234 …
**Engine :8000:** UP (3 agent roles loaded)
**Tests:** 5 collected (last run unknown)
**Sprint:** S1 — engine skeleton, analyzer TBD

### Recent commits
- abc1234 feat: add agent factory
- def5678 chore: scaffold ui
…
```

Keep it tight. No analysis, no suggestions — just facts. If the user wants a recommendation, they'll ask.
