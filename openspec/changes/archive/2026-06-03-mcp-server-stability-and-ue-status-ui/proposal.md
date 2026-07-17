## Why

The MCP server uses UDP multicast discovery and a shared Remote Execution socket, which creates a fragile dependency: status updates can only reach UE5 when the command channel is healthy, meaning a dropped connection leaves the toolbar label permanently stale and the server silently broken until a tool call is attempted. Users have no reliable visibility into whether the server is actually running.

## What Changes

- **New C++ UE5 plugin** (`UnrealMCPStatus`) with a dedicated Slate status bar widget and a lightweight TCP heartbeat listener on a fixed port (default 6690), completely independent of the Remote Execution protocol
- **Python heartbeat loop** added to `connection.py`: a background asyncio task sends a short heartbeat message to the C++ plugin port every 5 seconds while the server is running; the plugin shows "Stopped" after missing three consecutive heartbeats
- **Improved reconnection logic** in `UEConnection`: exponential backoff (1 s → 2 s → 4 s → 8 s, cap 30 s) replaces the current single-attempt retry; a `state` enum (`disconnected / connecting / connected / reconnecting`) replaces the `is_connected` bool flag
- **Clean shutdown sequence**: on SIGTERM/SIGINT or normal exit, the server sends an explicit `stopped` message over the heartbeat channel before closing, so the C++ plugin updates immediately instead of waiting for heartbeat timeout
- **Remove reliance on Python ToolMenus API** for status display; the current `unreal_mcp_status.py` provisioning and `push_ue_status()` calls become optional legacy compat that can be removed once the C++ plugin is deployed
- **BREAKING**: the `is_connected` attribute on `UEConnection` changes to a `state: ConnectionState` enum; callers checking `conn.is_connected` must switch to `conn.state == ConnectionState.CONNECTED`

## Capabilities

### New Capabilities

- `mcp-heartbeat-channel`: A persistent TCP heartbeat channel between the Python MCP server and UE5 editor, independent of the Remote Execution protocol, used to push server lifecycle events (connecting, connected, stopped) in real time
- `mcp-ue5-status-plugin`: A C++ UE5 editor plugin (`UnrealMCPStatus`) providing a Slate-based status bar widget driven by the heartbeat channel, with three visible states: Disconnected (grey), Connecting (yellow), Connected (green), and Stopped (red)

### Modified Capabilities

- `remote-connection`: Reconnection logic changes from single-attempt to exponential backoff with a `ConnectionState` enum; connection timeout and backoff parameters become configurable via environment variables
- `editor-mcp-status-indicator`: Status display moves from a Python ToolMenus toolbar button driven by Remote Execution to a C++ Slate widget driven by the heartbeat channel; Python-side provisioning (`unreal_mcp_status.py`, `init_unreal.py`) is deprecated

## Impact

- New files: `ue5-plugin/UnrealMCPStatus/` (C++ UE5 plugin, ~5 source files), `src/unreal_mcp/heartbeat.py`
- Modified files: `src/unreal_mcp/connection.py`, `src/unreal_mcp/server.py`, `src/unreal_mcp/provisioning.py`
- No changes to any MCP tools or the Remote Execution protocol itself
- UE5 project must add `UnrealMCPStatus` to its `.uproject` plugins list and rebuild; one-time setup
