## Context

The MCP server is an external Python process that connects *outward* to UE5 via the Remote Execution protocol (UDP discovery + TCP command channel). UE5 hosts the endpoint; the MCP server is the client. As a result, UE5 has no built-in awareness of whether an MCP client is connected — there is no existing hook or event to listen on from the editor side.

The only reliable channel for UE5 to receive data from the MCP server is the same Remote Execution Python execution pipeline that all tools use: the MCP server executes Python snippets inside the UE5 process.

## Goals / Non-Goals

**Goals:**
- Display a persistent toolbar label in the UE5 editor showing "MCP Connected" or "MCP Disconnected" with a color indicator.
- Update the label automatically when the MCP server connects or disconnects.
- Require zero manual setup from the user beyond placing a Python file in `Content/Python/`.

**Non-Goals:**
- Tracking multiple simultaneous MCP clients.
- Showing which tools are being called or a live activity log.
- Working during PIE sessions (editor toolbar is sufficient).
- A standalone UMG/Blueprint widget asset (Python-native ToolMenus approach keeps it zero-asset).

## Decisions

### 1. Use `unreal.ToolMenus` Python API for the toolbar entry

**Decision**: Register the status indicator as a ToolMenus section on the main toolbar via Python (`unreal.ToolMenus.get()`), which produces a native toolbar label/button without requiring any Blueprint or UMG assets.

**Why over EditorUtilityWidget**: An EditorUtilityWidget requires creating and saving a Blueprint asset, which adds friction and project pollution. `ToolMenus` is fully scriptable from Python and works immediately on load.

**Why over Slate Python Bridge**: Slate Python Bridge APIs are not consistently available across UE5 minor versions; `ToolMenus` is the documented, stable Python path.

### 2. MCP server pushes status updates via Python execution

**Decision**: The MCP server executes a short Python snippet inside UE5 (via the existing `conn.execute()` path) to update a module-level status variable immediately after connecting, and optionally on disconnect.

**Why over UE5 polling a file**: A file-based heartbeat is fragile (stale on crash) and requires a polling timer. Pushing the status update reuses the already-established Remote Execution channel with no extra infrastructure.

**Alternative considered**: A UDP heartbeat listener inside UE5 Python would work but adds a background thread and port management — unnecessary given the existing channel.

### 3. UE5-side module auto-loaded via `init_unreal.py`

**Decision**: Place `unreal_mcp_status.py` in `Content/Python/` and import it from `Content/Python/init_unreal.py`. UE5 automatically executes `init_unreal.py` at editor startup.

**Conflict mitigation**: The MCP server writes import guard logic — `init_unreal.py` is appended to (not overwritten) if it already exists, and the import line is idempotent (checked before writing).

### 4. Status stored as module-level global; toolbar rebuilt on each status push

**Decision**: `unreal_mcp_status.py` keeps a dict `_status = {"state": "disconnected", "updated_at": None}`. Each status push from the MCP server calls `set_status(state)`, which also calls `_rebuild_toolbar()` to re-register the ToolMenus entry with the new label/color. This is simpler than a live-updating timer.

**Why no polling timer on UE5 side**: A `threading.Timer` or `unreal.register_slate_tick_callback` add complexity and may interfere with garbage collection. The push model is sufficient because the status only changes when the MCP server connects or disconnects — both of which are observable moments.

## Risks / Trade-offs

| Risk | Mitigation |
|------|-----------|
| `init_unreal.py` already exists with conflicting content | MCP server appends a guarded import block; idempotent check prevents duplicate imports |
| ToolMenus Python API differs between UE5.1–5.5 | Wrap `_rebuild_toolbar()` in try/except with a fallback log; indicator silently absent rather than crashing startup |
| MCP crash leaves "Connected" label stale | Label shows last-pushed state — a stale "Connected" is cosmetically wrong but harmless. Future: add timestamp to tooltip |
| Disconnect status push may fail if connection is already gone | MCP server attempts a best-effort `execute()` on disconnect before closing the socket; failure is logged, not raised |

## Migration Plan

1. MCP server creates `Content/Python/unreal_mcp_status.py` on first connect if absent.
2. MCP server appends the import line to `Content/Python/init_unreal.py` (creating the file if needed).
3. User restarts the UE5 editor once for the `init_unreal.py` change to take effect.
4. On all subsequent MCP connections, the toolbar label updates automatically.

Rollback: delete `Content/Python/unreal_mcp_status.py` and remove the import line from `init_unreal.py`.
