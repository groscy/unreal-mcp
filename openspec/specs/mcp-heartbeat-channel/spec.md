## ADDED Requirements

### Requirement: C++ plugin exposes a TCP heartbeat listener
The `UnrealMCPStatus` C++ plugin SHALL open a TCP server socket on `localhost` at a configurable port (default 6690, overridable via UE console variable `mcp.HeartbeatPort`) when the editor starts. The listener SHALL accept exactly one concurrent client connection; a new incoming connection SHALL replace the previous one.

#### Scenario: Plugin starts with no Python server running
- **WHEN** the UE5 editor starts and no Python MCP server is running
- **THEN** the plugin SHALL have the TCP listener open and waiting, and the status widget SHALL display "MCP: Disconnected"

#### Scenario: Port already in use
- **WHEN** the plugin attempts to bind port 6690 and it is already in use
- **THEN** the plugin SHALL log a warning and skip the listener; the status widget SHALL display "MCP: Port in use"

### Requirement: Python server connects to the heartbeat listener on startup
The Python MCP server SHALL attempt to connect to the C++ plugin's TCP heartbeat port on startup (after the MCP server's asyncio loop is running). If the connection fails (UE5 not running or plugin not loaded), the failure SHALL be silently ignored and the server SHALL continue operating without a status UI.

#### Scenario: UE5 editor is running with the plugin loaded
- **WHEN** the Python MCP server starts and the C++ TCP listener is available on localhost:6690
- **THEN** the server SHALL establish a TCP connection and send `{"event":"connected","pid":<python_pid>}\n` within 2 seconds of startup

#### Scenario: UE5 editor is not running at startup
- **WHEN** the Python MCP server starts and no listener is reachable at localhost:6690
- **THEN** the connection attempt SHALL time out within 2 seconds, be silently ignored, and the server SHALL start normally

### Requirement: Python server sends periodic heartbeat messages
While the heartbeat TCP connection is open, the Python server SHALL send `{"event":"heartbeat"}\n` every 5 seconds (configurable via `UE_MCP_HEARTBEAT_INTERVAL` env var).

#### Scenario: Heartbeats received by C++ plugin
- **WHEN** the Python server is running and connected
- **THEN** the C++ plugin SHALL receive at least one `heartbeat` event within every 6-second window and SHALL maintain the "Connected" display state

#### Scenario: Heartbeats stop (Python server crashed or hung)
- **WHEN** the Python server stops sending heartbeats for more than 15 seconds (3 × interval)
- **THEN** the C++ plugin SHALL transition the status widget to "MCP: Stopped"

### Requirement: Python server sends a stopped event on clean shutdown
Before the Python MCP server exits (whether via SIGTERM, SIGINT, or normal completion), it SHALL send `{"event":"stopped"}\n` over the heartbeat connection and then close the socket.

#### Scenario: Clean server shutdown
- **WHEN** the Python MCP server is stopped cleanly (process exit, Ctrl-C)
- **THEN** the C++ plugin SHALL receive the `stopped` event and update the status widget to "MCP: Stopped" within 1 second of the event, without waiting for the heartbeat timeout

#### Scenario: Server crashes without sending stopped
- **WHEN** the Python server process is killed (SIGKILL or crash)
- **THEN** the TCP socket closes, the C++ plugin detects the connection drop, and the status widget transitions to "MCP: Stopped" immediately on socket close (not waiting for heartbeat timeout)

### Requirement: Heartbeat channel is independent of Remote Execution
The heartbeat TCP connection SHALL NOT share any socket, thread, or lock with the Remote Execution protocol channel. Failures on one SHALL NOT affect the other.

#### Scenario: Remote Execution drops while heartbeat is healthy
- **WHEN** the UE5 Remote Execution connection is lost mid-session but the Python server process is still running
- **THEN** the heartbeat channel SHALL continue operating, the status widget SHALL continue showing "MCP: Connected", and tool calls SHALL fail with a reconnection error (independent of status display)

#### Scenario: Heartbeat channel drops while Remote Execution is healthy
- **WHEN** the heartbeat TCP connection is interrupted (e.g., firewall rule)
- **THEN** Remote Execution tool calls SHALL continue working; the status widget MAY show "MCP: Stopped" after the timeout, which is acceptable given the unusual scenario
