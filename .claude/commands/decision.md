---
description: Record a lightweight architecture decision to docs/decisions/
user_invocable: true
---

Record a locked decision so future sessions don't re-litigate it. AgentTest doesn't have a heavy ADR process — just a one-page Markdown file in `docs/decisions/`.

## Input

`$ARGUMENTS` is the decision title in plain text, e.g.:
- `/decision keep FastAPI engine instead of pure CLI`
- `/decision rename api/ to engine/`

## Process

1. If `docs/decisions/` does not exist, create it.
2. Find the next available ID by listing existing files: `D-001-….md`, `D-002-….md`, … The new file is `D-NNN-<slug>.md` where `<slug>` is a kebab-cased version of the title.
3. Write the file with this template:

```markdown
# D-NNN: <title>

**Status:** Locked
**Date:** YYYY-MM-DD (today)
**Sprint:** S? (look up in docs/project_plan.md § 8)

## Context

(2–4 sentences. What problem? What forced the decision? Why now?)

## Options Considered

- **Option A** — pros / cons
- **Option B** — pros / cons
- **Option C** — pros / cons (if applicable)

## Decision

(1–2 sentences. The choice.)

## Rationale

(2–4 sentences. Why this option, not the others. Reference any relevant constraint from `docs/project_plan.md`.)

## Consequences

(What this commits us to. What it forecloses.)
```

4. Pre-fill what you can infer from conversation history. Leave the rest as `(TODO: fill in)`.
5. Show the file path and a one-line summary back to the user.

## Rules

- **One decision per file.** If the user lists multiple, ask which one to record now.
- **Do NOT auto-commit.** Just write the file.
- **Don't pad.** A 10-line decision is fine if 10 lines say it.
