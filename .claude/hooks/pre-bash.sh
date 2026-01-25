#!/bin/bash
# Pre-command hook for Bash tool
# Reads JSON from stdin, extracts command, runs validation
# Optimized for performance and subagent compatibility

set -e

# Read all input
INPUT=$(cat)

# Extract command safely
COMMAND=$(echo "$INPUT" | jq -r '.tool_input.command // empty' 2>/dev/null) || exit 0

# Skip if no command or empty
[ -z "$COMMAND" ] && exit 0

# Skip validation for simple/safe commands to improve performance
case "$COMMAND" in
  ls*|pwd|echo*|cat*|head*|tail*|grep*|find*|which*|env|git\ status*|git\ log*|git\ diff*)
    exit 0
    ;;
esac

# Check if claude-flow is available locally (faster than npx)
if command -v claude-flow &>/dev/null; then
  claude-flow hooks pre-command --command "$COMMAND" --validate-safety true 2>/dev/null || true
elif [ -x "./node_modules/.bin/claude-flow" ]; then
  ./node_modules/.bin/claude-flow hooks pre-command --command "$COMMAND" --validate-safety true 2>/dev/null || true
else
  # Fallback to npx only if necessary - use --yes to skip prompts
  npx --yes claude-flow hooks pre-command --command "$COMMAND" --validate-safety true 2>/dev/null || true
fi

exit 0
