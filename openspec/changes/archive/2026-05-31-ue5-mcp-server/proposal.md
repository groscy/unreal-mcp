## Why

AI assistants like Claude have no way to see or control an Unreal Engine 5 editor session today — every interaction requires manual copy-paste of data and hand-execution of commands. An MCP server built on UE5's built-in Python Remote Execution protocol closes that gap, giving Claude full, bidirectional access to a live editor without any custom C++ plugins or build toolchain setup.

## What Changes

- Introduce a standalone Python MCP server (`unreal-mcp`) that Claude (or any MCP client) connects to
- The server communicates with the UE5 editor via the Remote Execution protocol (UDP discovery + TCP command channel)
- Expose dedicated MCP tools covering actor/scene management, asset operations, Blueprint authoring, and editor control
- Expose a raw `execute_python` escape-hatch tool for arbitrary `unreal` Python execution (full trust, no guardrails)
- Expose MCP resources for read-only browsing of level hierarchy, asset tree, and world settings
- Ship with a README, example Claude Desktop config, and GitHub Actions CI

## Capabilities

### New Capabilities

- `remote-connection`: Manages the lifecycle of the Remote Execution protocol connection to UE5 (discovery, connect, disconnect, reconnect)
- `actor-management`: Create, delete, query, and transform actors in the active level
- `asset-management`: List, find, import, save, duplicate, and create assets in the Content Browser
- `blueprint-management`: Create blueprints, add variables/functions, compile, and call functions on blueprint instances
- `editor-control`: Start/stop Play-in-Editor, open/save levels, run console commands, get/set world settings
- `python-execution`: Execute arbitrary Python code in the UE5 editor context and return results
- `mcp-resources`: Read-only MCP resources exposing level hierarchy, asset tree, and world settings for browsable context

### Modified Capabilities

## Impact

- **New project**: no existing code affected
- **Runtime dependency**: UE5 editor must be running with the Python Editor Script Plugin and Remote Execution enabled
- **Python dependencies**: `mcp` SDK, plus the Remote Execution client (either the one bundled with UE or a standalone PyPI package)
- **Platform**: Windows-first (UE5 editor), with macOS support where UE5 supports it
- **Distribution**: PyPI package + GitHub repo; users configure via Claude Desktop `mcpServers` JSON
