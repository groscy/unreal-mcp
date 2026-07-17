## Context

UE5 ships a Python Editor Script Plugin that exposes the full `unreal` Python module inside the editor process. It also ships a Remote Execution subsystem: the editor listens on a UDP multicast address for discovery, then opens a TCP channel on which a client can send Python code strings and receive stdout + return values. This is the same channel used by the VS Code Unreal extension and UE's own `remote_execution.py` helper.

The MCP server sits between an MCP client (e.g. Claude Desktop) and a running UE5 editor session. All editor operations are expressed as `unreal` Python snippets sent over this channel.

## Goals / Non-Goals

**Goals:**
- Stable, low-friction connection to a running UE5 editor via Remote Execution
- A rich set of named MCP tools covering actors, assets, blueprints, and editor control
- A raw `execute_python` tool with full trust (no sandbox)
- MCP resources for browsable, read-only editor state
- Packaged as a `uv`-installable Python project; configurable via Claude Desktop `mcpServers` JSON
- Open-source, documented, CI-tested on GitHub

**Non-Goals:**
- Custom C++ UE plugin (no build toolchain required)
- Packaged game / runtime support (editor-only)
- Multi-editor / multi-project session management
- GUI or web dashboard
- Undo/redo tracking across tool calls

## Decisions

### 1. Transport: Remote Execution Protocol (not REST)

UE5 also ships a Remote Control REST API plugin. We use Remote Execution instead.

**Why:** Remote Control REST only exposes properties that Blueprint/C++ code explicitly registers. Remote Execution runs arbitrary `unreal` Python — giving access to every editor subsystem, asset registry, blueprint compiler, etc. without any UE-side registration work.

**Alternative considered:** REST API + WebSocket. Rejected: requires actors to opt in, can't drive the asset registry or blueprint graph arbitrarily.

### 2. Dedicated tools are thin Python-snippet generators

Each named tool (e.g. `place_actor`, `compile_blueprint`) constructs a small `unreal` Python snippet and sends it through the same Remote Execution channel as `execute_python`. There is no separate code path per tool on the UE side.

**Why:** Keeps the server code simple and testable without a live UE instance (snippet generation is pure Python). Also means `execute_python` is not a special case — it's the same primitive everything else builds on.

**Alternative considered:** Separate UE plugin that exposes a custom REST API per-tool. Rejected: requires C++ build, versioned plugin releases, installation friction.

### 3. Single persistent connection per server process

The server opens one Remote Execution connection at startup and holds it for the process lifetime. Tool calls reuse it; if it drops, the server attempts one reconnect before returning an error.

**Why:** Remote Execution's UDP discovery + TCP handshake adds ~100 ms latency. Reconnecting per tool call would be user-visible. A persistent connection makes tools feel instant.

**Trade-off:** If the editor restarts mid-session, the first tool call will trigger a reconnect, adding one round-trip of latency to that call.

### 4. Synchronous execution model

All tool calls block until the UE editor returns a result. No async queuing.

**Why:** MCP tool calls are already request-response. Remote Execution is synchronous. Adding async complexity (task IDs, polling) would complicate both the server and the prompts Claude writes.

**Trade-off:** Long-running operations (large imports, full recompiles) will block the MCP call for their duration. Acceptable for an editor assistant tool.

### 5. Structured return values as JSON

All tools return a JSON-serializable dict: `{"ok": true, "result": ...}` or `{"ok": false, "error": "..."}`. The `execute_python` tool additionally returns `{"stdout": "...", "result": ...}`.

**Why:** Claude can parse and reason about structured data. Free-text returns would require fragile string parsing.

### 6. Project layout: `src/` layout with `uv`

```
unreal-mcp/
├── src/
│   └── unreal_mcp/
│       ├── server.py        # MCP server + tool registration
│       ├── connection.py    # Remote Execution client wrapper
│       ├── tools/
│       │   ├── actors.py
│       │   ├── assets.py
│       │   ├── blueprints.py
│       │   ├── editor.py
│       │   └── python_exec.py
│       └── resources/
│           ├── level.py
│           ├── assets.py
│           └── world.py
├── tests/
├── pyproject.toml
├── README.md
└── .github/workflows/ci.yml
```

`uv` for dependency management and packaging. Entry point: `unreal-mcp` CLI that starts the MCP server in stdio mode.

### 7. MCP resources use URI scheme `unreal://`

Resources are addressed as:
- `unreal://level/hierarchy` — actor tree of the current level
- `unreal://content/tree` — content browser asset tree
- `unreal://world/settings` — world settings JSON

Resources always reflect live editor state (fetched on read, not cached).

## Risks / Trade-offs

**[Risk] UE editor not running when MCP server starts** → Mitigation: server starts successfully and returns a clear `{"ok": false, "error": "UE5 editor not reachable"}` on every tool call until a connection is established. Expose a `ping` tool for health checks.

**[Risk] Long-running operations block the MCP channel** → Mitigation: document expected durations in tool descriptions. For known-slow ops (bulk import), recommend Claude split them into smaller batches.

**[Risk] `execute_python` can corrupt project state** → Accepted trade-off: full trust mode is explicit and documented. Users who need guardrails can fork and remove the tool registration.

**[Risk] Remote Execution protocol changes between UE5 minor versions** → Mitigation: pin the `remote_execution.py` helper shipped with UE (copy into repo), test against each supported UE5 minor release via CI matrix.

**[Risk] Windows-only for most users** → Mitigation: use `pathlib` and avoid Windows-isms in server code; macOS support follows naturally. Note platform requirements clearly in README.

## Open Questions

- Should the server support SSE transport (for Claude.ai web) in addition to stdio? Defer to v2.
- Is there appetite for a `--readonly` flag that disables all write tools? Could be added without breaking changes.
