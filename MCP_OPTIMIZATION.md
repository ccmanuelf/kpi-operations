# MCP Tools Context Optimization

## Current Issue

The Claude Code diagnostics show a large MCP tools context (~60,962 tokens > 25,000 recommended):

| Server | Tools | Tokens |
|--------|-------|--------|
| claude-flow | 199 | ~22,677 |
| desktop-commander | 26 | ~13,105 |
| flow-nexus | 94 | ~12,052 |
| github | 26 | ~5,123 |
| ruv-swarm | 25 | ~3,435 |

## Optimization Strategies

### Option 1: Disable Rarely Used Servers (Recommended)

Edit `.mcp.json` and comment out or remove servers you don't frequently use:

```json
{
  "mcpServers": {
    // Keep essential servers
    "claude-flow": { ... },
    "github": { ... },
    
    // Comment out or remove less-used servers
    // "desktop-commander": { ... },
    // "flow-nexus": { ... },
    // "ruv-swarm": { ... }
  }
}
```

### Option 2: Use Project-Specific MCP Config

Create a lighter `.mcp.json` in this project directory with only the servers needed for KPI operations:

```json
{
  "mcpServers": {
    "github": {
      "command": "npx",
      "args": ["-y", "@modelcontextprotocol/server-github"],
      "env": {
        "GITHUB_PERSONAL_ACCESS_TOKEN": "your-token"
      },
      "type": "stdio"
    },
    "memory": {
      "command": "npx",
      "args": ["-y", "@modelcontextprotocol/server-memory"],
      "type": "stdio"
    }
  }
}
```

### Option 3: Use Deferred Tool Loading

Many tools are already deferred (loaded on demand via `ToolSearch`). This helps reduce initial context. The warning shows the total available tools, not actively loaded ones.

## Recommendations for This Project

For the KPI Operations project, the essential MCP servers are:
- **github**: For PR management and code reviews
- **memory**: For persistent context across sessions

Optional but useful:
- **claude-flow**: For swarm orchestration (if using multi-agent workflows)
- **taskmaster-ai**: For task management

The chat servers (mistral, deepseek, qwen, codestral) and desktop-commander can likely be removed for this project without impact.

## Verification

After modifying `.mcp.json`, restart Claude Code and run `/doctor` to verify reduced context usage.
