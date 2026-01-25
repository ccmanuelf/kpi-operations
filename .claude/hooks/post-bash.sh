#!/bin/bash
# Post-command hook for Bash tool
# Reads JSON from stdin, extracts results, updates metrics
# Optimized for performance - runs asynchronously

set -e

# Read all input
INPUT=$(cat)

# Extract command safely
COMMAND=$(echo "$INPUT" | jq -r '.tool_input.command // empty' 2>/dev/null) || exit 0

# Skip if no command or empty
[ -z "$COMMAND" ] && exit 0

# Skip metrics for simple commands to improve performance
case "$COMMAND" in
  ls*|pwd|echo*|cat*|head*|tail*|grep*|find*|which*|env)
    exit 0
    ;;
esac

# Run metrics collection in background (truly async, don't wait)
{
  if command -v claude-flow &>/dev/null; then
    claude-flow hooks post-command --command "$COMMAND" --track-metrics true 2>/dev/null
  elif [ -x "./node_modules/.bin/claude-flow" ]; then
    ./node_modules/.bin/claude-flow hooks post-command --command "$COMMAND" --track-metrics true 2>/dev/null
  fi
} &

# Don't wait - let it run in background
disown 2>/dev/null || true

exit 0
