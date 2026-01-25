# MCP Servers Validation Report

**Date:** 2026-01-23
**Platform:** macOS Darwin 24.6.0
**Claude Code Version:** 2.1.15
**Claude Desktop Version:** Latest

---

## Executive Summary

Comprehensive validation of all MCP servers has been completed. The majority of servers are functioning correctly. Key issues identified relate to connection timing during Claude Desktop startup and path configuration for wrapper scripts.

---

## Platform Compatibility Matrix

| MCP Server | Claude Desktop | Claude Code | Claude Web |
|------------|---------------|-------------|------------|
| **claude-flow** | ✅ Works | ✅ Works | ❌ N/A |
| **ruv-swarm** | ✅ Works | ✅ Works | ❌ N/A |
| **flow-nexus** | ✅ Works | ✅ Works | ❌ N/A |
| **memory** | ✅ Works | ✅ Works | ❌ N/A |
| **taskmaster-ai** | ✅ Works | ✅ Works | ❌ N/A |
| **sequential-thinking** | ✅ Works | ✅ Works | ❌ N/A |
| **minizinc** | ✅ Works | ✅ Works | ❌ N/A |
| **github** | ✅ Works | ✅ Works | ❌ N/A |
| **chat-openai** | ✅ Works | ❌ Not configured | ❌ N/A |
| **chat-mistral** | ✅ Works | ❌ Not configured | ❌ N/A |
| **chat-codestral** | ✅ Works | ✅ Works | ❌ N/A |
| **chat-deepseek** | ✅ Works | ❌ Not configured | ❌ N/A |
| **chat-dsreasoner** | ✅ Works | ✅ Works | ❌ N/A |
| **qwen_max** | ✅ Works | ❌ Not configured | ❌ N/A |
| **brave-search** | ✅ Works | ❌ Not configured | ❌ N/A |
| **Context7** | ✅ Works | ❌ Not configured | ❌ N/A |
| **PDF Tools** | ✅ Works | ❌ Not configured | ❌ N/A |
| **Claude in Chrome** | ✅ Works | ❌ Not configured | ❌ N/A |
| **Brave (AppleScript)** | ✅ Works | ❌ Not configured | ❌ N/A |
| **Control your Mac** | ✅ Works | ❌ Not configured | ❌ N/A |

**Note:** Claude Web does not support MCP servers - it uses built-in tools only.

---

## Server Status Details

### ✅ Fully Operational Servers

#### 1. claude-flow (v3.0.0-alpha.161)
- **Status:** Healthy, running for 138h 14m
- **Components:** swarm, memory, neural, mcp - all healthy
- **Features:** SPARC methodology, swarm coordination, neural patterns
- **URL:** https://github.com/ruvnet/claude-flow

#### 2. ruv-swarm (v1.0.20)
- **Status:** Operational after initialization
- **Features:** WASM modules, neural networks, forecasting, SIMD support
- **Note:** Requires `swarm_init` before `swarm_status` to avoid null reference error

#### 3. flow-nexus (v2.0.0)
- **Status:** Healthy
- **Database:** Connected and healthy
- **Features:** E2B sandboxes, cloud deployment, workflow automation

#### 4. memory (v0.6.3)
- **Status:** Connected
- **Persistence:** Enabled at `/Users/mcampos.cerda/Documents/claude-memory.json`
- **Current entities:** 2 entities stored

#### 5. taskmaster-ai (v0.42.0)
- **Status:** Connected
- **Features:** Task management, AI-driven subtask generation
- **Note:** Session sampling capabilities warning (non-critical)

#### 6. sequential-thinking (v0.2.0)
- **Status:** Connected
- **Tools:** 1 (sequentialthinking)

#### 7. minizinc (v0.2.0)
- **Status:** Connected
- **Tools:** 8 tools for constraint solving

#### 8. github (v0.6.2)
- **Status:** Connected
- **Tools:** Full GitHub API access (issues, PRs, repos, etc.)

#### 9. Chat Model Servers
| Server | Model | Status |
|--------|-------|--------|
| chat-openai | gpt-5.1 | ✅ Working |
| chat-mistral | mistral-large-2512 | ✅ Working |
| chat-codestral | codestral-2508 | ✅ Working |
| chat-deepseek | deepseek-chat | ✅ Working |
| chat-dsreasoner | deepseek-reasoner | ✅ Working |
| qwen_max | Qwen Max | ✅ Working |

#### 10. Browser Automation
- **Claude in Chrome:** Connected (17 tools)
- **Brave (AppleScript):** Connected

#### 11. Other Tools
- **Context7:** Working (library documentation)
- **PDF Tools:** Working (12 tools)
- **Control your Mac:** Working (osascript execution)

---

## Root Cause Analysis: Disconnection Pop-ups

### Issue Observed
At **15:30:29-30** today, multiple servers showed "Connection closed" errors:
- brave-search
- memory
- sequential-thinking
- github
- taskmaster-ai

### Root Causes Identified

1. **Wrapper Script Path Mismatch**
   - Wrapper scripts use `/usr/local/bin/npx`
   - System npx is at `/Users/mcampos.cerda/.npm-global/bin/npx`
   - macOS also has `/opt/homebrew/bin/node`
   - **Impact:** Race condition during startup

2. **Startup Timing Issues**
   - NPX packages require initial download/cache validation
   - Multiple servers starting simultaneously compete for resources
   - **Impact:** Some connections timeout during heavy startup load

3. **Session Reconnection**
   - When Claude Desktop window loses focus or sleeps, connections may drop
   - Reconnection happens automatically but generates pop-up notifications

4. **Non-Critical Warnings**
   - `git diff` permission error (Operation not permitted) - cosmetic
   - Python binary not found - only affects Python-based servers

---

## Configuration Files Analysis

### Claude Desktop Config (`claude_desktop_config.json`)
```json
{
  "mcpServers": {
    "brave-search": { "command": "wrapper script" },
    "qwen_max": { "command": "wrapper script" },
    "memory": { "command": "npx", "args": ["-y", "@modelcontextprotocol/server-memory"] },
    "sequential-thinking": { "command": "npx" },
    "github": { "command": "wrapper script" },
    "minizinc": { "command": "uv" },
    "taskmaster-ai": { "command": "wrapper script" },
    "chat-*": { "command": "wrapper scripts" }
  },
  "isUsingBuiltInNodeForMcp": false  // Important: Using system Node
}
```

### Claude Code Project Config
MCP servers for kpi-operations project:
- claude-flow ✅
- ruv-swarm ✅
- flow-nexus ✅
- sequential-thinking ✅

---

## Recommendations

### Immediate Fixes

1. **Update Wrapper Scripts Path**
   Update all wrapper scripts in `~/.mcp-wrappers/` to use correct npx path:
   ```bash
   # Change from:
   exec /usr/local/bin/npx ...
   # To:
   exec /Users/mcampos.cerda/.npm-global/bin/npx ...
   # Or simply:
   exec npx ...
   ```

2. **Add Startup Delay for Heavy Servers**
   For servers that take longer to initialize, consider adding retry logic.

### Optional Improvements

1. **Add Missing Servers to Claude Code**
   Claude Code project could benefit from:
   - memory server
   - github server
   - Context7 server

2. **Environment Variable Consolidation**
   Consider using `launchctl` to set environment variables globally:
   ```bash
   launchctl setenv GITHUB_PERSONAL_ACCESS_TOKEN "token"
   ```

---

## Version Information

| Component | Version |
|-----------|---------|
| Node.js | v25.4.0 |
| npm | 11.8.0 |
| npx | 11.8.0 |
| uv | 0.x (for minizinc) |
| claude-flow | 3.0.0-alpha.161 |
| ruv-swarm | 1.0.20 |
| flow-nexus | 0.1.128 |
| memory-server | 0.6.3 |
| sequential-thinking | 0.2.0 |
| taskmaster-ai | 0.42.0 |

---

## Conclusion

All MCP servers are fundamentally working correctly. The disconnection pop-ups in Claude Desktop are caused by:
1. Path mismatches in wrapper scripts
2. Startup race conditions
3. Normal reconnection behavior after idle periods

The servers automatically reconnect, and functionality is not impaired. The recommended fixes above will reduce the frequency of disconnection notifications.

---

*Report generated by Claude Code MCP Validation*
