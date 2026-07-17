## 1. UE5-Side Status Module

- [x] 1.1 Create `Content/Python/unreal_mcp_status.py` with module-level `_status` dict and `set_status(state)` function
- [x] 1.2 Implement `_rebuild_toolbar()` using `unreal.ToolMenus` to register/update a labeled toolbar entry in the main editor toolbar
- [x] 1.3 Wrap `_rebuild_toolbar()` in try/except so failures log a warning without crashing the import
- [x] 1.4 Call `_rebuild_toolbar()` at module import time to show the initial "MCP: Disconnected" state

## 2. UE5 Project Auto-Loading

- [x] 2.1 In the MCP server's provisioning logic, write `unreal_mcp_status.py` to the UE5 project's `Content/Python/` directory on first connect (skip if already exists)
- [x] 2.2 Append `import unreal_mcp_status` to `Content/Python/init_unreal.py` (create file if absent; guard against duplicate lines)
- [x] 2.3 Resolve the UE5 project path via the existing Remote Execution channel (execute Python to read `unreal.Paths.project_dir()`)

## 3. MCP Server Status Push

- [x] 3.1 Add a `push_ue_status(state: str)` helper in `connection.py` that executes a Python snippet calling `unreal_mcp_status.set_status(state)` in UE5
- [x] 3.2 Call `push_ue_status("connected")` after a successful `connect()` in `UEConnection.connect()`
- [x] 3.3 Call `push_ue_status("disconnected")` as a best-effort attempt in `UEConnection.disconnect()` before closing the socket (catch and log any failure)
- [x] 3.4 Log a warning (not exception) when the status push execution fails

## 4. Provisioning Integration

- [x] 4.1 Add a `provision_ue_status_module(conn: UEConnection)` function that orchestrates path resolution, file writing, and init_unreal.py patching
- [x] 4.2 Call `provision_ue_status_module()` from `_run()` in `server.py` immediately after a successful initial connection
- [x] 4.3 Skip provisioning silently if project path cannot be determined; log a warning

## 5. Verification

- [x] 5.1 Start the MCP server with UE5 running and confirm the toolbar shows "MCP: Connected"
- [x] 5.2 Stop the MCP server and confirm the toolbar updates to "MCP: Disconnected"
- [x] 5.3 Start a fresh UE5 editor session (without MCP) and confirm the toolbar shows "MCP: Disconnected" on load
- [x] 5.4 Confirm that running `provision_ue_status_module()` twice does not duplicate files or import lines
