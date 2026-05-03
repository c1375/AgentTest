#!/bin/bash
# Hook: PostToolUse (Edit|Write)
# Purpose: Warn when sync I/O patterns appear in engine/src/ async code paths.
#          Inspired by MyKefi's detect-blocking-calls.sh but adapted for Python.

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

# Only check Python files under engine/src/agenttest/
if ! echo "$FILE_PATH_NORM" | grep -qE 'engine/src/agenttest/.*\.py$'; then
    exit 0
fi

# Skip test files and CLI scripts
if echo "$FILE_PATH_NORM" | grep -qE '/(tests|eval)/'; then
    exit 0
fi

# Resolve actual file path on disk (Windows /c/ → c:/ etc.)
NORMALIZED_PATH=$(echo "$FILE_PATH" | sed 's|^/\([a-zA-Z]\)/|\1:/|')
ACTUAL_FILE="$FILE_PATH"
[ -f "$NORMALIZED_PATH" ] && ACTUAL_FILE="$NORMALIZED_PATH"
[ ! -f "$ACTUAL_FILE" ] && exit 0

VIOLATIONS=""

# requests library — synchronous, never use in async code
if grep -nE '^[^#]*\brequests\.(get|post|put|delete|patch|request)\(' "$ACTUAL_FILE" 2>/dev/null > /dev/null; then
    VIOLATIONS="${VIOLATIONS}WARNING: requests.* call in $FILE_PATH_NORM. Use httpx.AsyncClient instead.\n"
fi

# urllib.request — synchronous
if grep -nE '^[^#]*\burllib\.request\.' "$ACTUAL_FILE" 2>/dev/null > /dev/null; then
    VIOLATIONS="${VIOLATIONS}WARNING: urllib.request.* call in $FILE_PATH_NORM. Use httpx.AsyncClient instead.\n"
fi

# time.sleep — should be asyncio.sleep
if grep -nE '^[^#]*\btime\.sleep\(' "$ACTUAL_FILE" 2>/dev/null > /dev/null; then
    VIOLATIONS="${VIOLATIONS}WARNING: time.sleep() in $FILE_PATH_NORM. Use asyncio.sleep() instead.\n"
fi

# Sync Anthropic client
if grep -nE '^[^#]*\b(from anthropic import Anthropic\b|=\s*Anthropic\()' "$ACTUAL_FILE" 2>/dev/null > /dev/null; then
    VIOLATIONS="${VIOLATIONS}WARNING: synchronous Anthropic client in $FILE_PATH_NORM. Use AsyncAnthropic instead.\n"
fi

# Threading
if grep -nE '^[^#]*\bThread\(' "$ACTUAL_FILE" 2>/dev/null > /dev/null; then
    VIOLATIONS="${VIOLATIONS}WARNING: threading.Thread in $FILE_PATH_NORM. AgentTest uses asyncio, not threads. Use asyncio.create_task / TaskGroup.\n"
fi

if [ -n "$VIOLATIONS" ]; then
    printf '%b' "$VIOLATIONS" | python3 -c "
import json, sys
violations = sys.stdin.read().strip()
print(json.dumps({
    'hookSpecificOutput': {
        'hookEventName': 'PostToolUse',
        'additionalContext': violations
    }
}))
"
fi

exit 0
