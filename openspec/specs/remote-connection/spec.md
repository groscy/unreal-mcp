## ADDED Requirements

### Requirement: Server establishes connection on startup
The server SHALL attempt to connect to the UE5 Remote Execution endpoint when the MCP server process starts. Connection parameters (host, port, multicast group) SHALL be configurable via environment variables with sensible defaults matching UE5's built-in defaults. The connection lifecycle SHALL be tracked via a `ConnectionState` enum (`DISCONNECTED`, `CONNECTING`, `CONNECTED`, `RECONNECTING`) rather than a boolean flag. The `is_connected` attribute is removed; callers SHALL use `conn.state == ConnectionState.CONNECTED`.

#### Scenario: UE5 editor is running at startup
- **WHEN** the MCP server starts and a UE5 editor with Remote Execution enabled is reachable
- **THEN** the server SHALL establish a TCP connection, transition state to `CONNECTED`, and log a success message

#### Scenario: UE5 editor is not running at startup
- **WHEN** the MCP server starts and no UE5 editor is reachable within the connection timeout
- **THEN** the server SHALL start successfully in `DISCONNECTED` state without crashing and operate in a disconnected state

### Requirement: Tool calls fail gracefully when disconnected
The server SHALL return a structured error response for any tool call made while no UE5 connection is active (`state` is `DISCONNECTED` or `RECONNECTING`), rather than raising an unhandled exception. Tool calls SHALL NOT block waiting for a reconnect.

#### Scenario: Tool called with no active connection
- **WHEN** any MCP tool is invoked and `conn.state != ConnectionState.CONNECTED`
- **THEN** the tool SHALL return `{"ok": false, "error": "UE5 editor not connected. Ensure the editor is running with Remote Execution enabled."}` immediately without attempting a reconnect inline

### Requirement: Automatic reconnection with exponential backoff
If the Remote Execution connection drops mid-session, the server SHALL attempt to reconnect using exponential backoff managed by a background asyncio task. Inline tool calls SHALL NOT block on reconnection.

#### Scenario: Connection drops between tool calls
- **WHEN** the UE5 editor disconnects and a tool call is subsequently invoked
- **THEN** the tool SHALL return a connection error immediately; the background reconnect task SHALL attempt to reconnect after the current backoff delay (starting at 1 s, doubling on each failure up to 30 s cap)

#### Scenario: Reconnection succeeds after backoff
- **WHEN** the background reconnect task successfully re-establishes the RE connection
- **THEN** `conn.state` SHALL transition to `CONNECTED`, the backoff delay SHALL reset to 1 s, and subsequent tool calls SHALL succeed

#### Scenario: Repeated reconnection failures
- **WHEN** the RE endpoint is unreachable for an extended period
- **THEN** the backoff SHALL increase (1 → 2 → 4 → 8 → 16 → 30 s, then hold at 30 s) and the background task SHALL continue retrying without flooding logs (one log entry per attempt at DEBUG level, one at WARNING level every 5 failures)

### Requirement: Health check tool
The server SHALL expose a `ping` tool that reports the current connection status without executing any UE Python. It SHALL include the `ConnectionState` value in its response.

#### Scenario: Ping when connected
- **WHEN** `ping` is called and `conn.state == ConnectionState.CONNECTED`
- **THEN** it SHALL return `{"ok": true, "connected": true, "state": "connected", "ue_version": "<version string>"}`

#### Scenario: Ping when disconnected
- **WHEN** `ping` is called and `conn.state != ConnectionState.CONNECTED`
- **THEN** it SHALL return `{"ok": false, "connected": false, "state": "<state name>", "error": "<reason>"}`

### Requirement: Background async reconnect task
The server SHALL run a background `asyncio.Task` that manages RE reconnection while the MCP server is running. This task SHALL be the sole owner of reconnect attempts; inline tool execution SHALL NOT trigger reconnection.

#### Scenario: Background task starts at server launch
- **WHEN** `_run()` initialises the server
- **THEN** a background asyncio task SHALL be created that monitors `conn.state` and drives reconnect attempts with backoff when state is `RECONNECTING`

#### Scenario: Background task cleanup on shutdown
- **WHEN** the server begins shutting down
- **THEN** the background task SHALL be cancelled and awaited before the RE socket is closed
