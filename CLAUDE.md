# Claude Code Configuration - SPARC Development Environment

## 🚨 CRITICAL: CONCURRENT EXECUTION & FILE MANAGEMENT

**ABSOLUTE RULES**:
1. ALL operations MUST be concurrent/parallel in a single message
2. **NEVER save working files, text/mds and tests to the root folder**
3. ALWAYS organize files in appropriate subdirectories
4. **USE CLAUDE CODE'S TASK TOOL** for spawning agents concurrently, not just MCP

### ⚡ GOLDEN RULE: "1 MESSAGE = ALL RELATED OPERATIONS"

**MANDATORY PATTERNS:**
- **TodoWrite**: ALWAYS batch ALL todos in ONE call (5-10+ todos minimum)
- **Task tool (Claude Code)**: ALWAYS spawn ALL agents in ONE message with full instructions
- **File operations**: ALWAYS batch ALL reads/writes/edits in ONE message
- **Bash commands**: ALWAYS batch ALL terminal operations in ONE message
- **Memory operations**: ALWAYS batch ALL memory store/retrieve in ONE message

### 🎯 CRITICAL: Claude Code Task Tool for Agent Execution

**Claude Code's Task tool is the PRIMARY way to spawn agents:**
```javascript
// ✅ CORRECT: Use Claude Code's Task tool for parallel agent execution
[Single Message]:
  Task("Research agent", "Analyze requirements and patterns...", "researcher")
  Task("Coder agent", "Implement core features...", "coder")
  Task("Tester agent", "Create comprehensive tests...", "tester")
  Task("Reviewer agent", "Review code quality...", "reviewer")
  Task("Architect agent", "Design system architecture...", "system-architect")
```

**MCP tools are ONLY for coordination setup:**
- `mcp__claude-flow__swarm_init` - Initialize coordination topology
- `mcp__claude-flow__agent_spawn` - Define agent types for coordination
- `mcp__claude-flow__coordination_orchestrate` - Orchestrate high-level workflows

### 📁 File Organization Rules

**NEVER save to root folder. Use these directories:**
- `/src` - Source code files
- `/tests` - Test files
- `/docs` - Documentation and markdown files
- `/config` - Configuration files
- `/scripts` - Utility scripts
- `/examples` - Example code

## Project Overview

This project uses SPARC (Specification, Pseudocode, Architecture, Refinement, Completion) methodology with Claude-Flow orchestration for systematic Test-Driven Development.

## SPARC Commands

### Core Commands
- `npx claude-flow sparc modes` - List available modes
- `npx claude-flow sparc run <mode> "<task>"` - Execute specific mode
- `npx claude-flow sparc tdd "<feature>"` - Run complete TDD workflow
- `npx claude-flow sparc info <mode>` - Get mode details

### Batchtools Commands
- `npx claude-flow sparc batch <modes> "<task>"` - Parallel execution
- `npx claude-flow sparc pipeline "<task>"` - Full pipeline processing
- `npx claude-flow sparc concurrent <mode> "<tasks-file>"` - Multi-task processing

### Build Commands
- `npm run build` - Build project
- `npm run test` - Run tests
- `npm run lint` - Linting
- `npm run typecheck` - Type checking

## SPARC Workflow Phases

1. **Specification** - Requirements analysis (`sparc run spec-pseudocode`)
2. **Pseudocode** - Algorithm design (`sparc run spec-pseudocode`)
3. **Architecture** - System design (`sparc run architect`)
4. **Refinement** - TDD implementation (`sparc tdd`)
5. **Completion** - Integration (`sparc run integration`)

## Code Style & Best Practices

- **Modular Design**: Files under 500 lines
- **Environment Safety**: Never hardcode secrets
- **Test-First**: Write tests before implementation
- **Clean Architecture**: Separate concerns
- **Documentation**: Keep updated

## Agent Behavior Defaults

Behavior defaults for working in this repo. These govern *what* and *how much* to do; the concurrent-execution rules above govern *how to batch* tool calls once work is scoped.

- **Think before coding.** State assumptions; ask when requirements are ambiguous. If multiple interpretations exist, surface them — don't pick silently.
- **Smallest safe change first.** Minimum code that satisfies the requirement. No speculative abstractions, configurability, or error handling for impossible scenarios.
- **Surgical edits only.** Touch only what the task requires. No unrelated refactors, formatting churn, or "improvements" to adjacent code. Match existing style. If you spot unrelated dead code, mention it — don't delete it.
- **Define success before editing.** State the verifiable check (test name, endpoint + expected status, lint clean) before touching code.
- **Verify with the repo's existing workflow.** Backend: `pytest tests/` from `backend/` (no PYTHONPATH needed; coverage gate ≥75 %, current 81.88 %; pytest config in root `pyproject.toml`, coverage pool in `backend/.coveragerc`). Frontend: `npm run test`, `npm run lint`, coverage thresholds 32/25/25/34 (statements/branches/functions/lines, raised after Phase B.3). Smoke: `/health/live` on the API. Don't invent new validation paths.
- **CI must stay green.** Phase A.13 closed 2026-05-07 with main-branch CI green for the first time in 50+ commits. The 4 required-checks gate (`backend-tests`, `frontend-lint-and-tests`, `docker-build`, `e2e-sqlite`) must remain green; do NOT claim "tests pass" without verifying the latest run on `main` is `success` via `gh run list --branch main --limit 1`. Pre-commit hooks (`.pre-commit-config.yaml`) catch most failures before they reach CI; install with `pre-commit install` after clone — see `docs/CONTRIBUTING.md`.
- **Permissive assertions are forbidden.** No `assert response.status_code in [...]`. Each test asserts ONE expected code. Phase B.2 cleaned up 778 such patterns; new ones get rejected at review.
- **Self-audit findings expand scope; no tech debt allowed.** During a deliberate verification pass, anything found — even pre-existing issues beyond your own changes — becomes part of the current task and must be fixed before presenting. This activates only when auditing; it does not override *Surgical edits only* during the baseline task.
- **Multi-agent swarms are opt-in.** Default to a single direct edit. Spawn the Task tool or MCP swarm only when the task is genuinely parallel or large enough to warrant the coordination overhead.

Source: behavioral defaults adapted from `forrestchang/andrej-karpathy-skills`. Project-specific rules elsewhere in this file take precedence on conflict.

## Token Efficiency (RTK)

RTK (Rust Token Killer) is a CLI proxy installed via Homebrew that compresses shell command output by 60–90 %. The PreToolUse hook lives in `~/.claude/settings.json` (global scope, applies to every project) and transparently rewrites most bash commands as `rtk <cmd>`. Per-tool bypasses live in `~/Library/Application Support/rtk/config.toml` under `[hooks].exclude_commands`. Verify live savings with `rtk gain`.

- **Prefer shell over built-in tools when scanning files.** Use `cat`, `rg`, `find`, `head`, `tail` instead of Read/Grep/Glob — only the shell path passes through rtk's compressor, so file-inspection savings only land when you go through bash. Keep Read/Grep/Glob for exact paths, specific line ranges, or unmodified content (e.g., reading a file you'll then `Edit`).
- **These pass through unmodified (output is verbatim):** `curl`, `docker exec`, `docker compose exec` (hardcoded in the rtk binary), `docker logs`, `docker compose logs`, `pytest` (also catches `PYTHONPATH=.. pytest` — rtk strips env-var prefixes before matching), `npm install`, `npx playwright test`, `alembic revision`, `weasyprint`. Everything else gets rewritten as `rtk <cmd>`.
- **Matcher is looser than the entry names suggest.** For Docker (which rtk has a built-in wrapper for), bypass is subcommand-strict — `docker run`, `docker build`, `docker compose ps` still get rewritten. For tools rtk doesn't know, the matcher is case-insensitive first-token-prefix, so `alembic revision` actually bypasses every `alembic <subcmd>` and `npm install` bypasses any unrecognized `npm <subcmd>` (e.g., `npm test`, `npm ci`). `curl` also matches `curlie`, `Curl`, `curl-impersonate` — none are used here, but worth knowing.
- **On failure, read the tee log before re-running.** Compressed failure output prints the full tee log path at the end — open it first. Re-running silently re-incurs the cost without surfacing new information the log already contains.
- **Frontend test triage.** Vue 3.4 + Vuetify 3.5 + AG Grid generic `ColDef<T>` errors cascade — one bad type produces dozens of follow-on diagnostics that compress well but obscure the root cause. With 1,982 Vitest tests across 80 files and 546 Playwright tests across 15 files (3 browser projects), failures-only mode is the right default for both; if you ever remove `npx playwright test` from `exclude_commands`, re-verify the trace artifact path is still printed on failure before trusting compressed output.

## 🚀 Available Agents (54 Total)

### Core Development
`coder`, `reviewer`, `tester`, `planner`, `researcher`

### Swarm Coordination
`hierarchical-coordinator`, `mesh-coordinator`, `adaptive-coordinator`, `collective-intelligence-coordinator`, `swarm-memory-manager`

### Consensus & Distributed
`byzantine-coordinator`, `raft-manager`, `gossip-coordinator`, `consensus-builder`, `crdt-synchronizer`, `quorum-manager`, `security-manager`

### Performance & Optimization
`perf-analyzer`, `performance-benchmarker`, `task-orchestrator`, `memory-coordinator`, `smart-agent`

### GitHub & Repository
`github-modes`, `pr-manager`, `code-review-swarm`, `issue-tracker`, `release-manager`, `workflow-automation`, `project-board-sync`, `repo-architect`, `multi-repo-swarm`

### SPARC Methodology
`sparc-coord`, `sparc-coder`, `specification`, `pseudocode`, `architecture`, `refinement`

### Specialized Development
`backend-dev`, `mobile-dev`, `ml-developer`, `cicd-engineer`, `api-docs`, `system-architect`, `code-analyzer`, `base-template-generator`

### Testing & Validation
`tdd-london-swarm`, `production-validator`

### Migration & Planning
`migration-planner`, `swarm-init`

## 🎯 Claude Code vs MCP Tools

### Claude Code Handles ALL EXECUTION:
- **Task tool**: Spawn and run agents concurrently for actual work
- File operations (Read, Write, Edit, MultiEdit, Glob, Grep)
- Code generation and programming
- Bash commands and system operations
- Implementation work
- Project navigation and analysis
- TodoWrite and task management
- Git operations
- Package management
- Testing and debugging

### MCP Tools ONLY COORDINATE:
- Swarm initialization (topology setup)
- Agent type definitions (coordination patterns)
- Task orchestration (high-level planning)
- Memory management
- Neural features
- Performance tracking
- GitHub integration

**KEY**: MCP coordinates the strategy, Claude Code's Task tool executes with real agents.

## 🚀 Quick Setup

```bash
# Add MCP servers (Claude Flow required, others optional)
# claude-flow@alpha was renamed to ruflo (v3); pin the version to avoid surprise breaking changes
claude mcp add claude-flow npx -y ruflo@3.10.42 mcp start
claude mcp add ruv-swarm npx ruv-swarm mcp start  # Optional: Enhanced coordination
claude mcp add flow-nexus npx flow-nexus@latest mcp start  # Optional: Cloud features
```

## MCP Tool Categories

### Coordination
`swarm_init`, `agent_spawn`, `task_create`, `coordination_orchestrate`

### Monitoring
`swarm_status`, `swarm_health`, `agent_list`, `agent_status`, `task_status`, `task_summary`

### Memory & Neural
`memory_store`, `memory_retrieve`, `memory_search`, `neural_status`, `neural_train`, `neural_patterns`

### GitHub Integration
`github_repo_analyze`, `github_pr_manage`, `github_issue_track`, `github_workflow`, `github_metrics`

### System
`system_health`, `performance_benchmark`, `performance_report`

### Flow-Nexus MCP Tools (Optional Advanced Features)
Flow-Nexus extends MCP capabilities with 70+ cloud-based orchestration tools:

**Key MCP Tool Categories:**
- **Swarm & Agents**: `swarm_init`, `swarm_scale`, `agent_spawn`, `task_orchestrate`
- **Sandboxes**: `sandbox_create`, `sandbox_execute`, `sandbox_upload` (cloud execution)
- **Templates**: `template_list`, `template_deploy` (pre-built project templates)
- **Neural AI**: `neural_train`, `neural_patterns`, `seraphina_chat` (AI assistant)
- **GitHub**: `github_repo_analyze`, `github_pr_manage` (repository management)
- **Real-time**: `execution_stream_subscribe`, `realtime_subscribe` (live monitoring)
- **Storage**: `storage_upload`, `storage_list` (cloud file management)

**Authentication Required:**
- Register: `mcp__flow-nexus__user_register` or `npx flow-nexus@latest register`
- Login: `mcp__flow-nexus__user_login` or `npx flow-nexus@latest login`
- Access 70+ specialized MCP tools for advanced orchestration

## 🚀 Agent Execution Flow with Claude Code

### The Correct Pattern:

1. **Optional**: Use MCP tools to set up coordination topology
2. **REQUIRED**: Use Claude Code's Task tool to spawn agents that do actual work
3. **REQUIRED**: Each agent runs hooks for coordination
4. **REQUIRED**: Batch all operations in single messages

### Example Full-Stack Development:

```javascript
// Single message with all agent spawning via Claude Code's Task tool
[Parallel Agent Execution]:
  Task("Backend Developer", "Build REST API with Express. Use hooks for coordination.", "backend-dev")
  Task("Frontend Developer", "Create React UI. Coordinate with backend via memory.", "coder")
  Task("Database Architect", "Design PostgreSQL schema. Store schema in memory.", "code-analyzer")
  Task("Test Engineer", "Write Jest tests. Check memory for API contracts.", "tester")
  Task("DevOps Engineer", "Setup Docker and CI/CD. Document in memory.", "cicd-engineer")
  Task("Security Auditor", "Review authentication. Report findings via hooks.", "reviewer")

  // All todos batched together
  TodoWrite { todos: [...8-10 todos...] }

  // All file operations together
  Write "backend/server.js"
  Write "frontend/App.jsx"
  Write "database/schema.sql"
```

## 📋 Agent Coordination Protocol

### Every Agent Spawned via Task Tool MUST:

**1️⃣ BEFORE Work:**
```bash
npx claude-flow@alpha hooks pre-task --description "[task]"
npx claude-flow@alpha hooks session-restore --session-id "swarm-[id]"
```

**2️⃣ DURING Work:**
```bash
npx claude-flow@alpha hooks post-edit --file "[file]" --memory-key "swarm/[agent]/[step]"
npx claude-flow@alpha hooks notify --message "[what was done]"
```

**3️⃣ AFTER Work:**
```bash
npx claude-flow@alpha hooks post-task --task-id "[task]"
npx claude-flow@alpha hooks session-end --export-metrics true
```

## 🎯 Concurrent Execution Examples

### ✅ CORRECT WORKFLOW: MCP Coordinates, Claude Code Executes

```javascript
// Step 1: MCP tools set up coordination (optional, for complex tasks)
[Single Message - Coordination Setup]:
  mcp__claude-flow__swarm_init { topology: "mesh", maxAgents: 6 }
  mcp__claude-flow__agent_spawn { type: "researcher" }
  mcp__claude-flow__agent_spawn { type: "coder" }
  mcp__claude-flow__agent_spawn { type: "tester" }

// Step 2: Claude Code Task tool spawns ACTUAL agents that do the work
[Single Message - Parallel Agent Execution]:
  // Claude Code's Task tool spawns real agents concurrently
  Task("Research agent", "Analyze API requirements and best practices. Check memory for prior decisions.", "researcher")
  Task("Coder agent", "Implement REST endpoints with authentication. Coordinate via hooks.", "coder")
  Task("Database agent", "Design and implement database schema. Store decisions in memory.", "code-analyzer")
  Task("Tester agent", "Create comprehensive test suite with 90% coverage.", "tester")
  Task("Reviewer agent", "Review code quality and security. Document findings.", "reviewer")

  // Batch ALL todos in ONE call
  TodoWrite { todos: [
    {id: "1", content: "Research API patterns", status: "in_progress", priority: "high"},
    {id: "2", content: "Design database schema", status: "in_progress", priority: "high"},
    {id: "3", content: "Implement authentication", status: "pending", priority: "high"},
    {id: "4", content: "Build REST endpoints", status: "pending", priority: "high"},
    {id: "5", content: "Write unit tests", status: "pending", priority: "medium"},
    {id: "6", content: "Integration tests", status: "pending", priority: "medium"},
    {id: "7", content: "API documentation", status: "pending", priority: "low"},
    {id: "8", content: "Performance optimization", status: "pending", priority: "low"}
  ]}

  // Parallel file operations
  Bash "mkdir -p app/{src,tests,docs,config}"
  Write "app/package.json"
  Write "app/src/server.js"
  Write "app/tests/server.test.js"
  Write "app/docs/API.md"
```

### ❌ WRONG (Multiple Messages):
```javascript
Message 1: mcp__claude-flow__swarm_init
Message 2: Task("agent 1")
Message 3: TodoWrite { todos: [single todo] }
Message 4: Write "file.js"
// This breaks parallel coordination!
```

## Performance Benefits

- **84.8% SWE-Bench solve rate**
- **32.3% token reduction**
- **2.8-4.4x speed improvement**
- **27+ neural models**

## Hooks Integration

### Pre-Operation
- Auto-assign agents by file type
- Validate commands for safety
- Prepare resources automatically
- Optimize topology by complexity
- Cache searches

### Post-Operation
- Auto-format code
- Train neural patterns
- Update memory
- Analyze performance
- Track token usage

### Session Management
- Generate summaries
- Persist state
- Track metrics
- Restore context
- Export workflows

## Advanced Features (v2.0.0)

- 🚀 Automatic Topology Selection
- ⚡ Parallel Execution (2.8-4.4x speed)
- 🧠 Neural Training
- 📊 Bottleneck Analysis
- 🤖 Smart Auto-Spawning
- 🛡️ Self-Healing Workflows
- 💾 Cross-Session Memory
- 🔗 GitHub Integration

## Integration Tips

1. Start with basic swarm init
2. Scale agents gradually
3. Use memory for context
4. Monitor progress regularly
5. Train patterns from success
6. Enable hooks automation
7. Use GitHub tools first

## Support

- Documentation: https://github.com/ruvnet/claude-flow
- Issues: https://github.com/ruvnet/claude-flow/issues
- Flow-Nexus Platform: https://flow-nexus.ruv.io (registration required for cloud features)

---

Remember: **Claude Flow coordinates, Claude Code creates!**

# Codebase Audit Status (Run 7)
**Current audit:** Run 7 (Fable5) — report at `_audit/RUN-7-FABLE5-AUDIT.md`. Opened at grade **B−**; both criticals and all gate-integrity Highs are now remediated.
**Previous runs:** Runs 1–4 in `_audit/_history/`; Run 5 phase reports + `PHASE-7-CONSOLIDATION.md` in `_audit/`; Run 6 in `_audit/RUN-6-BUSINESS-AUDIT/`. The `_audit/` tree is local-only (gitignored), so these reports do NOT survive a fresh clone.

### Run 7 remediation — SHIPPED (merged to main, each verified on the Render demo)
- **C-1** demo auto-seed/`drop_all` gated behind `DEMO_MODE` (was ungated — could wipe a real DB on boot)
- **C-2** `/api/auth/register` locked to demo-mode + role `operator` only (was unauthenticated, accepted caller-supplied `admin`)
- **H-1** DB-backed token revocation: `TOKEN_BLACKLIST` table keyed by JWT `jti` (was in-memory set, lost on restart)
- **H-2** password-reset token no longer logged; **H-4** 7× `detail=str(exc)` removed
- **H-3/H-5** honest coverage gate (`backend/.coveragerc`, measures prod code; 81.88% / threshold 75) + single pytest config with deprecation guards re-armed
- **H-6** blocking `detect-secrets` (committed `.secrets.baseline`) + **M-14** blocking `pip-audit` in CI
- **M-3** Simulation V1 HTTP API removed (past sunset); **M-6** `orm/`↔`schemas/` invariant corrected; **M-7** uniform 3-tier authorization on all mutation endpoints; **M-9** capacity 400→500
- Deps: starlette PYSEC-2026-161 + esbuild advisories patched; Node 22 / Python 3.11

### Resolved since the report
- **python-jose → pyjwt** (M-15): all auth on PyJWT 2.13.0; ecdsa/pyasn1 pins dropped.
- **Role model reconciled** (was the open product decision): `UserRole` now formalizes all six roles (admin, poweruser, leader, supervisor, operator, viewer); the user-management regex accepts the same six; guard tiers are admin / planner / supervisory / contributor (= everyone but viewer) / authenticated. Viewer is enforced read-only on transactional data-entry endpoints. Pinned by `test_permission_matrix.py`.

### Still open (lower-priority Run 7 items)
- Python lockfile/hash pinning (L); `endpoints/csv_upload.py` consolidation (L); ~55 residual hardcoded i18n strings (L); `.mcp.json.example` template (L)
- Architecture Mediums deferred: single schema-evolution mechanism (Alembic vs `create_all`), `main.py` lifespan decomposition

### Audit Conventions
- Audit reports in `_audit/` (current run at root, prior runs in subdirs/`_history/`)
- Subagent temp files go in `_audit/temp/`
- No code modifications without explicit user approval
- Write findings to disk immediately after each sub-section

# important-instruction-reminders
Do what has been asked; nothing more, nothing less.
NEVER create files unless they're absolutely necessary for achieving your goal.
ALWAYS prefer editing an existing file to creating a new one.
NEVER proactively create documentation files (*.md) or README files. Only create documentation files if explicitly requested by the User.
Never save working files, text/mds and tests to the root folder.
See "Agent Behavior Defaults" above for clarify-first, surgical-edit, and success-criteria rules.
