#!/bin/bash
# Post-edit hook for Write/Edit/MultiEdit tools
# Reads JSON from stdin, extracts file path, updates memory
# Optimized for performance - runs asynchronously

set -e

# Read all input
INPUT=$(cat)

# Extract file path safely (try both field names)
FILE_PATH=$(echo "$INPUT" | jq -r '.tool_input.file_path // .tool_input.path // empty' 2>/dev/null) || exit 0

# Skip if no file path or empty
[ -z "$FILE_PATH" ] && exit 0

# Skip memory update for non-code files
case "$FILE_PATH" in
  *.md|*.txt|*.json|*.yaml|*.yml|*.log|*.csv)
    exit 0
    ;;
esac

# Run memory update in background (truly async, don't wait)
{
  if command -v claude-flow &>/dev/null; then
    claude-flow hooks post-edit --file "$FILE_PATH" --update-memory true 2>/dev/null
  elif [ -x "./node_modules/.bin/claude-flow" ]; then
    ./node_modules/.bin/claude-flow hooks post-edit --file "$FILE_PATH" --update-memory true 2>/dev/null
  fi
} &

# Don't wait - let it run in background
disown 2>/dev/null || true

exit 0
