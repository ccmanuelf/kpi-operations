#!/bin/bash
# Set MCP environment variables at launchd level (persists for GUI apps)
# Run this after boot or when updating API keys

set -e

# Source secrets if available
if [ -f ~/.mcp-secrets ]; then
  source ~/.mcp-secrets
  echo "Loaded secrets from ~/.mcp-secrets"
fi

# List of required environment variables
VARS=(
  "ANTHROPIC_API_KEY"
  "PERPLEXITY_API_KEY"
  "DEEPSEEK_API_KEY"
  "MISTRAL_API_KEY"
  "GITHUB_PERSONAL_ACCESS_TOKEN"
)

echo "Setting environment variables at launchd level..."

for var in "${VARS[@]}"; do
  val="${!var}"
  if [ -n "$val" ]; then
    launchctl setenv "$var" "$val"
    echo "  ✓ $var set (${#val} chars)"
  else
    echo "  ⚠ $var not found in environment, skipping"
  fi
done

echo ""
echo "Done! Environment variables are now available to GUI applications."
echo "Run 'scripts/mcp-health-check.sh' to verify."
