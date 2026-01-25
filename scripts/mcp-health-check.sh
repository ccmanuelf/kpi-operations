#!/bin/bash
# MCP Health Check - Accurate diagnostics for this project
# Replaces false positives from `claude doctor` for MCP env var checks

set -e

GREEN='\033[0;32m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
NC='\033[0m' # No Color
CHECK="✓"
WARN="⚠"
CROSS="✗"

echo ""
echo "╔════════════════════════════════════════════════════════════════╗"
echo "║              MCP Server Health Check                           ║"
echo "╚════════════════════════════════════════════════════════════════╝"
echo ""

# Check launchd environment variables
echo "┌─ Environment Variables (launchd level) ─────────────────────────"
env_ok=true
for key in ANTHROPIC_API_KEY PERPLEXITY_API_KEY DEEPSEEK_API_KEY MISTRAL_API_KEY GITHUB_PERSONAL_ACCESS_TOKEN; do
  val=$(launchctl getenv "$key" 2>/dev/null || echo "")
  if [ -n "$val" ]; then
    len=${#val}
    masked="${val:0:4}...${val: -4}"
    printf "│ ${GREEN}${CHECK}${NC} %-30s ${GREEN}SET${NC} (%d chars: %s)\n" "$key" "$len" "$masked"
  else
    printf "│ ${RED}${CROSS}${NC} %-30s ${RED}NOT SET${NC}\n" "$key"
    env_ok=false
  fi
done
echo "└────────────────────────────────────────────────────────────────"
echo ""

# Check ~/.mcp-secrets exists and is secure
echo "┌─ Secrets File ───────────────────────────────────────────────────"
if [ -f ~/.mcp-secrets ]; then
  perms=$(stat -f "%Lp" ~/.mcp-secrets 2>/dev/null || stat -c "%a" ~/.mcp-secrets 2>/dev/null)
  if [ "$perms" = "600" ]; then
    printf "│ ${GREEN}${CHECK}${NC} ~/.mcp-secrets exists with secure permissions (600)\n"
  else
    printf "│ ${YELLOW}${WARN}${NC} ~/.mcp-secrets exists but permissions are $perms (should be 600)\n"
  fi
else
  printf "│ ${YELLOW}${WARN}${NC} ~/.mcp-secrets not found (optional if using launchctl)\n"
fi
echo "└────────────────────────────────────────────────────────────────"
echo ""

# Check wrapper scripts
echo "┌─ Wrapper Scripts (~/.mcp-wrappers/) ────────────────────────────"
if [ -d ~/.mcp-wrappers ]; then
  wrapper_count=$(ls ~/.mcp-wrappers/*.sh 2>/dev/null | wc -l | tr -d ' ')
  printf "│ ${GREEN}${CHECK}${NC} Directory exists with %s wrapper scripts\n" "$wrapper_count"
  for script in ~/.mcp-wrappers/*.sh; do
    if [ -x "$script" ]; then
      printf "│   ${GREEN}${CHECK}${NC} %s (executable)\n" "$(basename "$script")"
    else
      printf "│   ${RED}${CROSS}${NC} %s (not executable)\n" "$(basename "$script")"
    fi
  done
else
  printf "│ ${YELLOW}${WARN}${NC} ~/.mcp-wrappers/ not found\n"
fi
echo "└────────────────────────────────────────────────────────────────"
echo ""

# Check MCP config
echo "┌─ MCP Configuration (.mcp.json) ─────────────────────────────────"
MCP_CONFIG="$(pwd)/.mcp.json"
if [ -f "$MCP_CONFIG" ]; then
  printf "│ ${GREEN}${CHECK}${NC} .mcp.json found\n"
  servers=$(grep -o '"[^"]*":' "$MCP_CONFIG" | grep -v "mcpServers\|command\|args\|env\|type" | tr -d '":' | head -20)
  for server in $servers; do
    printf "│   • %s\n" "$server"
  done
else
  printf "│ ${RED}${CROSS}${NC} .mcp.json not found in current directory\n"
fi
echo "└────────────────────────────────────────────────────────────────"
echo ""

# Summary
echo "┌─ Summary ────────────────────────────────────────────────────────"
if $env_ok; then
  printf "│ ${GREEN}${CHECK} All required environment variables are set at launchd level${NC}\n"
  printf "│ ${GREEN}${CHECK} MCP servers should work correctly${NC}\n"
  printf "│\n"
  printf "│ ${YELLOW}Note:${NC} 'claude doctor' may show false warnings about missing\n"
  printf "│ environment variables. This is a known issue - the vars ARE set.\n"
else
  printf "│ ${RED}${CROSS} Some environment variables are missing${NC}\n"
  printf "│ Run: source ~/.mcp-secrets && ./scripts/set-launchd-env.sh\n"
fi
echo "└────────────────────────────────────────────────────────────────"
echo ""
