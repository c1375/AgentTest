#!/bin/bash
# Hook: PreToolUse (Bash)
# Purpose: Block destructive shell commands. Heavily inspired by MyKefi's version,
#          adapted for AgentTest (Python + Docker, single dev).

INPUT=$(cat)

COMMAND=$(echo "$INPUT" | python3 -c "
import sys, json
try:
    data = json.load(sys.stdin)
    print(data.get('tool_input', {}).get('command', ''))
except:
    print('')
" 2>/dev/null)

DENY_REASON=""

# Block rm -rf on broad/root paths
if echo "$COMMAND" | grep -qE 'rm\s+(-[a-zA-Z]*r[a-zA-Z]*f|-[a-zA-Z]*f[a-zA-Z]*r)\s+(/\s|/\*|~/|\.\s*$|\.\.\s*$|/[cd]/|//[cd]/)'; then
    DENY_REASON="Blocked: rm -rf on broad path. Specify the exact target."
fi

# Block force push to main/master
if [ -z "$DENY_REASON" ] && echo "$COMMAND" | grep -qiE 'git\s+push\s+[^|;]*(-f|--force)[^|;]*(main|master)'; then
    DENY_REASON="Blocked: force push to main/master. Use a feature branch + PR workflow."
elif [ -z "$DENY_REASON" ] && echo "$COMMAND" | grep -qiE 'git\s+push\s+[^|;]*(main|master)[^|;]*(-f|--force)'; then
    DENY_REASON="Blocked: force push to main/master. Use a feature branch + PR workflow."
fi

# Block docker volume rm — would wipe any persisted engine data
if [ -z "$DENY_REASON" ] && echo "$COMMAND" | grep -qE 'docker\s+volume\s+rm'; then
    DENY_REASON="Blocked: docker volume rm would wipe AgentTest's persisted engine data. Run it manually outside Claude Code if you really mean it."
fi

# Block git reset --hard
if [ -z "$DENY_REASON" ] && echo "$COMMAND" | grep -qE 'git\s+reset\s+--hard'; then
    DENY_REASON="Blocked: git reset --hard discards uncommitted changes irreversibly. If you truly want to discard, run it manually."
fi

# Block git clean -f
if [ -z "$DENY_REASON" ] && echo "$COMMAND" | grep -qE 'git\s+clean\s+-[a-zA-Z]*f'; then
    DENY_REASON="Blocked: git clean -f deletes untracked files irreversibly. If you really mean it, run it manually."
fi

if [ -n "$DENY_REASON" ]; then
    printf '%s' "$DENY_REASON" | python3 -c "
import json, sys
reason = sys.stdin.read().strip()
print(json.dumps({
    'hookSpecificOutput': {
        'hookEventName': 'PreToolUse',
        'permissionDecision': 'deny',
        'permissionDecisionReason': reason
    }
}))
"
    exit 0
fi

exit 0
