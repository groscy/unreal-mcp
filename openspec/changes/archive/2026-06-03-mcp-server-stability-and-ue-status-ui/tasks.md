## 1. Python: ConnectionState enum and UEConnection refactor

- [x] 1.1 Add `ConnectionState` enum (`DISCONNECTED`, `CONNECTING`, `CONNECTED`, `RECONNECTING`) to `connection.py`
- [x] 1.2 Replace `is_connected: bool` with `state: ConnectionState` on `UEConnection`; add `_reconnect_delay: float` and `_reconnect_attempts: int` fields
- [x] 1.3 Update `connect()` to set `state = CONNECTING` on entry, `CONNECTED` on success, `DISCONNECTED` on failure
- [x] 1.4 Update `disconnect()` to set `state = DISCONNECTED`
- [x] 1.5 Update `execute()` to check `conn.state == ConnectionState.CONNECTED` instead of `is_connected`; remove inline reconnect from `execute()` — return error immediately if not connected
- [x] 1.6 Update `ping()` to include `"state": conn.state.value` in its response dict
- [x] 1.7 Update all internal callers of `is_connected` in `server.py`, `provisioning.py`, and any tool modules

## 2. Python: Exponential backoff reconnect task

- [x] 2.1 Create `src/unreal_mcp/reconnect.py` with `run_reconnect_loop(conn: UEConnection)` async function that monitors `conn.state` and retries RE connection with backoff (1 → 2 → 4 → 8 → 16 → 30 s cap)
- [x] 2.2 Add log throttling to reconnect loop: DEBUG per attempt, WARNING every 5 consecutive failures
- [x] 2.3 Wire the reconnect task into `server.py`'s `_run()` using `asyncio.create_task()`; cancel and await it in the `finally` block

## 3. Python: Heartbeat channel

- [x] 3.1 Create `src/unreal_mcp/heartbeat.py` with `HeartbeatClient` class that holds a TCP connection to `localhost:6690` (configurable via `UE_MCP_HEARTBEAT_PORT`)
- [x] 3.2 Implement `HeartbeatClient.connect()`: async connect with 2 s timeout; return `True`/`False`; silence connection-refused errors
- [x] 3.3 Implement `HeartbeatClient.send(event: str, **kwargs)`: write `{"event": event, ...}\n` to the socket; silently drop if not connected
- [x] 3.4 Implement `run_heartbeat_loop(client: HeartbeatClient)` async function: send `connected` event once on connection, then send `heartbeat` every 5 s (configurable via `UE_MCP_HEARTBEAT_INTERVAL`)
- [x] 3.5 On `asyncio.CancelledError` (clean shutdown), send `stopped` event before returning from the heartbeat loop
- [x] 3.6 Wire `HeartbeatClient` into `server.py`'s `_run()`: connect on startup (non-fatal), start heartbeat task, cancel and await on shutdown

## 4. C++ Plugin: Project structure

- [x] 4.1 Create `ue5-plugin/UnrealMCPStatus/UnrealMCPStatus.uplugin` with module descriptor (Editor-only, `LoadingPhase: PostEngineInit`)
- [x] 4.2 Create `ue5-plugin/UnrealMCPStatus/Source/UnrealMCPStatus/UnrealMCPStatus.Build.cs` with dependencies: `Core`, `CoreUObject`, `Engine`, `Sockets`, `Networking`, `Slate`, `SlateCore`, `ToolMenus`, `LevelEditor`
- [x] 4.3 Create `ue5-plugin/UnrealMCPStatus/Source/UnrealMCPStatus/Public/UnrealMCPStatusModule.h` with `IModuleInterface` declaration
- [x] 4.4 Create directory `ue5-plugin/UnrealMCPStatus/Source/UnrealMCPStatus/Private/`

## 5. C++ Plugin: Heartbeat TCP listener

- [x] 5.1 Create `MCPHeartbeatListener.h/.cpp`: class with `Start(int Port)`, `Stop()`, and a delegate/callback `OnEventReceived(FString EventType, int32 Pid)` that fires on the game thread
- [x] 5.2 Implement the listener using UE's `FSocket` / `ISocketSubsystem` API; run accept-and-read loop on a background `FRunnable` thread
- [x] 5.3 Parse incoming newline-delimited JSON using `FJsonSerializer`; extract `event` and `pid` fields
- [x] 5.4 Handle socket close (EOF) by firing `OnEventReceived("closed", 0)` so the widget can transition to Stopped
- [x] 5.5 Handle bind failure (port in use): log warning, skip listening

## 6. C++ Plugin: Status toolbar widget

- [x] 6.1 Create `SMCPStatusWidget.h/.cpp`: a `SCompoundWidget` that holds a current `EMCPStatus` enum (`Disconnected`, `Connecting`, `Connected`, `Stopped`) and renders a colored `STextBlock`
- [x] 6.2 Implement `SetStatus(EMCPStatus)` on the widget; use `STextBlock::SetText` and `STextBlock::SetColorAndOpacity` for the four states (grey / yellow / green / red)
- [x] 6.3 Implement tooltip text per state as specified in `mcp-ue5-status-plugin` spec (including PID in Connected state)
- [x] 6.4 Add heartbeat timeout detection: a `FTimerHandle` (or periodic task) that fires every second, increments a missed-heartbeat counter, and calls `SetStatus(Stopped)` after 3 × interval seconds with no heartbeat

## 7. C++ Plugin: Module wiring

- [x] 7.1 Implement `UnrealMCPStatusModule.cpp`: `StartupModule()` creates the listener on port 6690, registers the `SMCPStatusWidget` in the `LevelEditor.LevelEditorToolBar.PlayToolBar` menu via `UToolMenus`, and connects `OnEventReceived` to `SetStatus` calls on the widget
- [x] 7.2 Implement `ShutdownModule()`: stop the listener, unregister the toolbar entry
- [x] 7.3 Register the module implementation with `IMPLEMENT_MODULE`

## 8. Documentation and deprecation

- [x] 8.1 Add deprecation comment to `provisioning.py` and `push_ue_status()` in `connection.py` indicating they will be removed once the C++ plugin is adopted
- [x] 8.2 Update project README with C++ plugin installation instructions (copy to `Plugins/`, add to `.uproject`, regenerate project files, rebuild)
- [x] 8.3 Update README "Troubleshooting" section: note that `UE_MCP_HEARTBEAT_PORT` and `mcp.HeartbeatPort` must match; note the 15-second timeout before Stopped state appears after a crash
