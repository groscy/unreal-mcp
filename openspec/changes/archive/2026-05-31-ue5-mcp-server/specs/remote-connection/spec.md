## ADDED Requirements

### Requirement: Server establishes connection on startup
The server SHALL attempt to connect to the UE5 Remote Execution endpoint when the MCP server process starts. Connection parameters (host, port, multicast group) SHALL be configurable via environment variables with sensible defaults matching UE5's built-in defaults.

#### Scenario: UE5 editor is running at startup
- **WHEN** the MCP server starts and a UE5 editor with Remote Execution enabled is reachable
- **THEN** the server SHALL establish a TCP connection and log a success message

#### Scenario: UE5 editor is not running at startup
- **WHEN** the MCP server starts and no UE5 editor is reachable within the connection timeout
- **THEN** the server SHALL start successfully without crashing and operate in a disconnected state

### Requirement: Tool calls fail gracefully when disconnected
The server SHALL return a structured error response for any tool call made while no UE5 connection is active, rather than raising an unhandled exception.

#### Scenario: Tool called with no active connection
- **WHEN** any MCP tool is invoked and the server has no active Remote Execution connection
- **THEN** the tool SHALL return `{"ok": false, "error": "UE5 editor not connected. Ensure the editor is running with Remote Execution enabled."}`

### Requirement: Automatic reconnection on connection loss
If the Remote Execution connection drops mid-session, the server SHALL attempt one reconnect before the next tool call fails.

#### Scenario: Connection drops between tool calls
- **WHEN** the UE5 editor disconnects and a tool call is subsequently invoked
- **THEN** the server SHALL attempt to reconnect once, execute the tool if reconnection succeeds, and return a connection error only if reconnection fails

### Requirement: Health check tool
The server SHALL expose a `ping` tool that reports the current connection status without executing any UE Python.

#### Scenario: Ping when connected
- **WHEN** `ping` is called and the server has an active connection
- **THEN** it SHALL return `{"ok": true, "connected": true, "ue_version": "<version string>"}`

#### Scenario: Ping when disconnected
- **WHEN** `ping` is called and no connection is active
- **THEN** it SHALL return `{"ok": false, "connected": false, "error": "<reason>"}`
