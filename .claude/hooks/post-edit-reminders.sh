#!/bin/bash
# Hook: PostToolUse (Edit|Write)
# Purpose: After editing certain files, remind about follow-up actions
#          (reinstall deps, restart server, mirror sibling file).

INPUT=$(cat)

FILE_PATH=$(echo "$INPUT" | python3 -c "
import sys, json
try:
    data = json.load(sys.stdin)
    print(data.get('tool_input', {}).get('file_path', ''))
except:
    print('')
" 2>/dev/null)

FILE_PATH_NORM=$(echo "$FILE_PATH" | sed 's|\\|/|g')

REMINDERS=""

case "$FILE_PATH_NORM" in
    */engine/pyproject.toml)
        REMINDERS="Edited engine/pyproject.toml — run \`cd engine && pip install -e \".[dev]\"\` to pick up dependency changes."
        ;;
    */engine/configs/agents.yaml)
        REMINDERS="Edited agents.yaml — restart uvicorn (the AgentClientFactory builds clients at startup; YAML edits do not hot-reload)."
        ;;
    */docs/project_plan.md)
        REMINDERS="Edited docs/project_plan.md — if this was a substantive change, mirror it in docs/project_plan.zh.md (the two are kept in sync)."
        ;;
    */docs/project_plan.zh.md)
        REMINDERS="Edited docs/project_plan.zh.md — if this was a substantive change, mirror it in docs/project_plan.md (the two are kept in sync)."
        ;;
    */engine/src/agenttest/agents/role.py)
        REMINDERS="Edited agents/role.py — make sure agents.yaml has a matching entry for any role you added/removed. The factory iterates AgentRole and looks each one up in YAML."
        ;;
esac

if [ -n "$REMINDERS" ]; then
    printf '%s' "$REMINDERS" | python3 -c "
import json, sys
reminders = sys.stdin.read()
print(json.dumps({
    'hookSpecificOutput': {
        'hookEventName': 'PostToolUse',
        'additionalContext': reminders
    }
}))
"
fi

exit 0
