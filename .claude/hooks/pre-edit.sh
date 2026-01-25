#!/bin/bash
# Pre-edit hook for Write/Edit/MultiEdit tools
# Reads JSON from stdin, extracts file path, provides context
# Optimized for performance and reliability

set -e

# Read all input
INPUT=$(cat)

# Extract file path safely (try both field names)
FILE_PATH=$(echo "$INPUT" | jq -r '.tool_input.file_path // .tool_input.path // empty' 2>/dev/null) || exit 0

# Skip if no file path or empty
[ -z "$FILE_PATH" ] && exit 0

# Skip context loading for non-code files to improve performance
case "$FILE_PATH" in
  *.md|*.txt|*.json|*.yaml|*.yml|*.log|*.csv)
    exit 0
    ;;
esac

# Check if claude-flow is available locally (faster than npx)
if command -v claude-flow &>/dev/null; then
  claude-flow hooks pre-edit --file "$FILE_PATH" --load-context true 2>/dev/null || true
elif [ -x "./node_modules/.bin/claude-flow" ]; then
  ./node_modules/.bin/claude-flow hooks pre-edit --file "$FILE_PATH" --load-context true 2>/dev/null || true
fi

# Don't use npx fallback for pre-edit - too slow and not critical
exit 0
