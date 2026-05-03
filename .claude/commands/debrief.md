---
description: End-of-session debrief — what was done, what's next, what to remember
user_invocable: true
---

End-of-session debrief. Summarize what was accomplished, decisions made, and what's next. Helps the next session pick up cold.

## Data to Collect

1. **Conversation review**: scan this session's tool calls and user messages. What concrete things changed? What decisions were made? What patterns emerged?
2. **Git state**: `git log --oneline -10` to see what was committed (if git is initialized)
3. **File changes**: which files were `Write`d / `Edit`ed this session
4. **Memory check**: which session learnings should be saved as `feedback`, `project`, or `reference` memory? Existing memory lives at `~/.claude/projects/E-----Generative-AI-AgentTest/memory/`.

## Output Format

```
## Session Debrief — YYYY-MM-DD

### Done this session
- (concrete deliverables, one bullet each)

### Decisions locked
| Decision | Choice | Why |
|---|---|---|
| … | … | (1 sentence) |

### Files touched
- engine/…

### Open / next
- (what's unfinished or up next per docs/project_plan.md sprint plan)

### Memory updates
- (✅ or ❌) feedback memory: …
- (✅ or ❌) project memory: …
- (✅ or ❌) reference memory: …
```

## Rules

- Be concise. Each bullet ≤ 1 line.
- Focus on **decisions and rationale**, not narration ("we discussed X" → "decided X because Y").
- ALWAYS check whether memory needs updating — this is the last chance before context is lost.
- If anything was non-obvious or surprising about how the user wanted things done, save it as a `feedback` memory immediately, not "later".
- End with: "Next session can pick up by running `/status` then opening `docs/project_plan.md` § 8."
