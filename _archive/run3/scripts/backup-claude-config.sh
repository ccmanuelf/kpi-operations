#!/bin/bash
# Backup Claude Code configuration before migration to native installer

set -e

TIMESTAMP=$(date +%Y%m%d_%H%M%S)
BACKUP_DIR="$HOME/.claude-backup-$TIMESTAMP"
PROJECT_DIR="/Users/mcampos.cerda/Documents/Programming/kpi-operations"

echo "🔄 Creating Claude Code configuration backup..."
echo "📁 Backup directory: $BACKUP_DIR"

mkdir -p "$BACKUP_DIR"

# Backup global config
if [ -f "$HOME/.claude.json" ]; then
    cp "$HOME/.claude.json" "$BACKUP_DIR/claude.json"
    echo "✅ Backed up ~/.claude.json"
fi

# Backup global settings directory
if [ -d "$HOME/.claude" ]; then
    cp -r "$HOME/.claude" "$BACKUP_DIR/dot-claude"
    echo "✅ Backed up ~/.claude/ directory"
fi

# Backup project-level configs
if [ -d "$PROJECT_DIR/.claude" ]; then
    cp -r "$PROJECT_DIR/.claude" "$BACKUP_DIR/project-dot-claude"
    echo "✅ Backed up project .claude/ directory"
fi

if [ -f "$PROJECT_DIR/.mcp.json" ]; then
    cp "$PROJECT_DIR/.mcp.json" "$BACKUP_DIR/project-mcp.json"
    echo "✅ Backed up project .mcp.json"
fi

# Create a manifest
cat > "$BACKUP_DIR/MANIFEST.txt" << EOF
Claude Code Configuration Backup
================================
Created: $(date)
Backup Directory: $BACKUP_DIR

Files backed up:
- claude.json (from ~/.claude.json)
- dot-claude/ (from ~/.claude/)
- project-dot-claude/ (from $PROJECT_DIR/.claude/)
- project-mcp.json (from $PROJECT_DIR/.mcp.json)

To restore, run:
  $PROJECT_DIR/scripts/restore-claude-config.sh $BACKUP_DIR
EOF

echo ""
echo "✅ Backup complete!"
echo "📁 Backup location: $BACKUP_DIR"
echo ""
echo "Next steps:"
echo "  1. Uninstall npm version: npm uninstall -g @anthropic-ai/claude-code"
echo "  2. Install native version: curl -fsSL https://claude.ai/install.sh | sh"
echo "  3. Verify: $PROJECT_DIR/scripts/verify-claude-config.sh"
