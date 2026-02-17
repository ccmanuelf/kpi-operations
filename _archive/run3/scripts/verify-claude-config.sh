#!/bin/bash
# Verify Claude Code configuration after migration

PROJECT_DIR="/Users/mcampos.cerda/Documents/Programming/kpi-operations"
ERRORS=0

echo "🔍 Verifying Claude Code configuration..."
echo ""

# Check Claude version
echo "📌 Claude Code Version:"
if command -v claude &> /dev/null; then
    claude --version
else
    echo "❌ Claude command not found"
    ERRORS=$((ERRORS + 1))
fi
echo ""

# Check global config
echo "📌 Global Configuration (~/.claude.json):"
if [ -f "$HOME/.claude.json" ]; then
    echo "✅ File exists"
    # Check for MCP servers
    MCP_COUNT=$(grep -c '"command"' "$HOME/.claude.json" 2>/dev/null || echo "0")
    echo "   MCP server entries found: $MCP_COUNT"
else
    echo "❌ File not found"
    ERRORS=$((ERRORS + 1))
fi
echo ""

# Check global settings
echo "📌 Global Settings (~/.claude/settings.json):"
if [ -f "$HOME/.claude/settings.json" ]; then
    echo "✅ File exists"
    cat "$HOME/.claude/settings.json"
else
    echo "⚠️  File not found (may be normal)"
fi
echo ""

# Check project config
echo "📌 Project Configuration ($PROJECT_DIR/.claude/):"
if [ -d "$PROJECT_DIR/.claude" ]; then
    echo "✅ Directory exists"
    ls -la "$PROJECT_DIR/.claude/"
else
    echo "❌ Directory not found"
    ERRORS=$((ERRORS + 1))
fi
echo ""

# Check project MCP config
echo "📌 Project MCP Config ($PROJECT_DIR/.mcp.json):"
if [ -f "$PROJECT_DIR/.mcp.json" ]; then
    echo "✅ File exists"
    # List MCP servers
    echo "   MCP servers configured:"
    grep -o '"[^"]*":.*{' "$PROJECT_DIR/.mcp.json" | grep -v mcpServers | sed 's/"//g' | sed 's/:.*//' | sed 's/^/     - /'
else
    echo "❌ File not found"
    ERRORS=$((ERRORS + 1))
fi
echo ""

# Check hooks
echo "📌 Hooks Configuration:"
if [ -d "$PROJECT_DIR/.claude/hooks" ]; then
    echo "✅ Hooks directory exists"
    ls "$PROJECT_DIR/.claude/hooks/" 2>/dev/null | sed 's/^/     - /'
else
    echo "⚠️  Hooks directory not found"
fi
echo ""

# Try to list MCP servers if claude is available
echo "📌 MCP Server Status (from claude mcp list):"
if command -v claude &> /dev/null; then
    claude mcp list 2>/dev/null || echo "   (Run 'claude mcp list' manually to check)"
else
    echo "   Cannot check - claude command not available"
fi
echo ""

# Summary
echo "================================"
if [ $ERRORS -eq 0 ]; then
    echo "✅ All configuration checks passed!"
else
    echo "❌ Found $ERRORS issue(s). Review output above."
fi
echo "================================"

exit $ERRORS
