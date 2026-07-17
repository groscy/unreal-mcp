## Context

The MCP server communicates with UE5 exclusively via the Remote Execution (RE) protocol — a UDP multicast discovery phase followed by a TCP command channel. All status updates pushed to the UE5 toolbar also travel over this same channel (Python executes `import unreal_mcp_status; unreal_mcp_status.set_status(...)` via RE). This creates a hard dependency: if RE is unavailable (UE5 not launched, network hiccup, mid-session disconnect), the toolbar label permanently shows a stale state and any tool call silently fails until the connection is re-established.

Additionally, the reconnect strategy in `UEConnection.execute()` is a single synchronous attempt with no delay; repeated fast failures from an aggressive MCP client can flood logs and block the asyncio event loop for seconds at a time.

## Goals / Non-Goals

**Goals:**
- Toolbar status in UE5 is always accurate regardless of RE health — including showing "Stopped" when the Python process exits
- Reconnection to RE uses exponential backoff to avoid log spam and hot-loop CPU waste
- Clean shutdown sends an explicit stopped signal before socket close so the C++ plugin updates immediately
- Python server's connection state is represented as an enum (`ConnectionState`) to eliminate boolean flag ambiguity
- No user action required to get the status indicator working — the C++ plugin auto-loads with UE5

**Non-Goals:**
- Replacing the Remote Execution protocol for tool dispatch
- Changing any existing MCP tool behavior or interface
- Supporting non-UE5 targets or remote (non-localhost) editors
- Backwards compatibility shim for the deprecated `is_connected` bool attribute

## Decisions

### Decision 1: C++ plugin owns the display; Python owns the connection channel

**Chosen:** A new C++ UE5 plugin (`UnrealMCPStatus`) listens on a dedicated TCP port (default `localhost:6690`). The Python server connects to this port on startup and sends heartbeat messages. The C++ plugin updates its Slate widget directly — no Remote Execution involved.

**Alternatives considered:**
- *Keep Python ToolMenus display, add a separate RE-independent ping:* still requires RE alive to update the label after reconnect; the stopped-state problem remains.
- *UE5 HTTP endpoint polled by Python:* HTTP in C++ requires pulling in the HTTP module and is heavier; polling adds latency; server-push (Python → C++) is simpler.
- *File-based IPC (write a status file, C++ watches it):* fragile on Windows (file locks, polling interval), harder to detect clean vs. crash exits.

**Rationale:** TCP is already in UE's socket API. A persistent connection from Python makes disconnect detection instant (socket close = server gone). The C++ plugin needs ~3 source files.

### Decision 2: C++ plugin listens; Python connects

**Chosen:** C++ plugin TCP listener on `localhost:6690` accepts incoming Python connections. Python tries to connect once on startup; if the plugin is not loaded (UE5 not running), the failure is silently swallowed and the server operates without a status UI.

**Alternative:** Python listens, C++ polls — requires Python to expose an extra port, adds a polling delay, and the server process must bind a port before the C++ plugin even runs.

**Rationale:** UE5 is typically already running when the MCP server starts (the user launched it from the toolbar or from their MCP config). C++ listener is always ready; Python just connects.

### Decision 3: Heartbeat message format — newline-delimited JSON

```
{"event":"connected","pid":<int>}\n
{"event":"heartbeat"}\n
{"event":"stopped"}\n
```

Simple, human-readable, zero external dependencies. The C++ side parses with `FJsonSerializer` (already in Engine).

### Decision 4: Heartbeat interval 5 s, timeout 3 missed = 15 s

C++ plugin marks server as "Stopped" after 15 seconds of silence. This is short enough to feel responsive but long enough to tolerate a brief Python GC pause or system load spike. Both values are configurable via UE console variables (`mcp.HeartbeatIntervalSeconds`, `mcp.HeartbeatTimeoutBeats`).

### Decision 5: ConnectionState enum replaces is_connected bool

```python
class ConnectionState(enum.Enum):
    DISCONNECTED = "disconnected"
    CONNECTING   = "connecting"
    CONNECTED    = "connected"
    RECONNECTING = "reconnecting"
```

The `is_connected` property is **removed** (breaking change). All internal callers are updated in the same PR.

### Decision 6: Exponential backoff for RE reconnects

Initial delay 1 s, multiplier 2×, cap 30 s. Delay is tracked on `UEConnection` and reset to 1 s on successful connect. A `reconnect_attempts` counter is exposed for observability. The background async task owns the retry loop; individual tool calls do not retry inline anymore — they return an error immediately if state is not `CONNECTED`, which gives the AI client a fast error to work with rather than blocking.

### Decision 7: Background asyncio tasks, not threads

`server.py` is already an asyncio program (`asyncio.run(_run())`). Both the heartbeat sender and the RE reconnect loop are `asyncio.Task` objects created in `_run()`. This avoids thread-safety concerns with `_re` (RemoteExecution socket).

### Decision 8: C++ plugin source lives in repo under `ue5-plugin/`

Users copy (or symlink) `ue5-plugin/UnrealMCPStatus/` into their project's `Plugins/` directory and add it to `.uproject`. A README explains the one-time setup. This keeps the plugin version-locked to the server version.

## Risks / Trade-offs

- **[Risk] C++ plugin compilation required** → users must have UE5 source headers and rebuild; mitigation: document clearly, provide pre-built binary for common UE5 versions if demand warrants.
- **[Risk] Port 6690 conflicts** → mitigated by `UE_MCP_HEARTBEAT_PORT` env var on Python side and `mcp.HeartbeatPort` CVar on C++ side.
- **[Risk] Breaking change on `is_connected`** → only affects internal code (`connection.py`, `server.py`); no external callers documented; mitigated by changing all usages in the same commit.
- **[Risk] Heartbeat loop keeps asyncio loop busy if UE5 unreachable at startup** → mitigated by `asyncio.wait_for` with a 2 s connect timeout; failure is non-fatal.
- **[Trade-off] C++ plugin is optional** → if user doesn't install it, status display falls back to the legacy Python ToolMenus provisioning path (kept as deprecated fallback). This means both code paths exist temporarily.

## Migration Plan

1. Ship Python changes (`connection.py`, `server.py`, `heartbeat.py`) — fully backwards-compatible on the Python side as long as no external code reads `is_connected`.
2. Ship C++ plugin source in `ue5-plugin/UnrealMCPStatus/`.
3. Update README with installation instructions for the C++ plugin.
4. In a follow-up change, remove the Python provisioning path (`provisioning.py`, `push_ue_status()`) once the C++ plugin is confirmed working.

## Open Questions

- Should the C++ plugin be packaged as a `.uplugin` that UE5 Marketplace distributes, or always source-only? (Assumption: source-only for now, marketplace optional later.)
- Do we need the heartbeat TCP listener to support multiple simultaneous Python connections (e.g., two MCP server instances)? (Assumption: single connection; last writer wins.)
