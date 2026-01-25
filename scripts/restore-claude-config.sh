#!/bin/bash
# Restore Claude Code configuration from backup

set -e

BACKUP_DIR="$1"
PROJECT_DIR="/Users/mcampos.cerda/Documents/Programming/kpi-operations"

if [ -z "$BACKUP_DIR" ]; then
    echo "❌ Usage: $0 <backup-directory>"
    echo ""
    echo "Available backups:"
    ls -d ~/.claude-backup-* 2>/dev/null || echo "  No backups found"
    exit 1
fi

if [ ! -d "$BACKUP_DIR" ]; then
    echo "❌ Backup directory not found: $BACKUP_DIR"
    exit 1
fi

echo "🔄 Restoring Claude Code configuration from backup..."
echo "📁 Backup directory: $BACKUP_DIR"
echo ""

# Restore global config
if [ -f "$BACKUP_DIR/claude.json" ]; then
    cp "$BACKUP_DIR/claude.json" "$HOME/.claude.json"
    echo "✅ Restored ~/.claude.json"
fi

# Restore global settings directory
if [ -d "$BACKUP_DIR/dot-claude" ]; then
    # Remove current and restore
    rm -rf "$HOME/.claude"
    cp -r "$BACKUP_DIR/dot-claude" "$HOME/.claude"
    echo "✅ Restored ~/.claude/ directory"
fi

# Restore project-level configs
if [ -d "$BACKUP_DIR/project-dot-claude" ]; then
    rm -rf "$PROJECT_DIR/.claude"
    cp -r "$BACKUP_DIR/project-dot-claude" "$PROJECT_DIR/.claude"
    echo "✅ Restored project .claude/ directory"
fi

if [ -f "$BACKUP_DIR/project-mcp.json" ]; then
    cp "$BACKUP_DIR/project-mcp.json" "$PROJECT_DIR/.mcp.json"
    echo "✅ Restored project .mcp.json"
fi

echo ""
echo "✅ Restore complete!"
echo ""
echo "Run verification: $PROJECT_DIR/scripts/verify-claude-config.sh"
