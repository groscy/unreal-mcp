## MODIFIED Requirements

### Requirement: Server establishes connection on startup
The server SHALL attempt to connect to the UE5 Remote Execution endpoint when the MCP server process starts, using the connection strategy selected by `UE_CONNECT_MODE` (default `auto`). The initial connection attempt SHALL NOT block the MCP server's asyncio event loop or its initialization handshake; the background reconnect task SHALL own the first connection attempt. Connection parameters (connect mode, command host/port, RE bind host, multicast group, command read timeout) SHALL be configurable via environment variables with sensible defaults matching UE5's built-in defaults (including a multicast bind default of `127.0.0.1`). The connection lifecycle SHALL be tracked via a `ConnectionState` enum (`DISCONNECTED`, `CONNECTING`, `CONNECTED`, `RECONNECTING`).

#### Scenario: UE5 editor is running at startup
- **WHEN** the MCP server starts and a UE5 editor with Remote Execution enabled is reachable
- **THEN** the server SHALL establish the TCP command channel via the selected connection mode, transition state to `CONNECTED`, and log a success message — without having blocked the event loop during startup

#### Scenario: UE5 editor is not running at startup
- **WHEN** the MCP server starts and no UE5 editor is reachable
- **THEN** the server SHALL complete its MCP initialization immediately in `CONNECTING`/`DISCONNECTED` state without blocking or crashing, and the background reconnect task SHALL keep retrying

## ADDED Requirements

### Requirement: Discovery-free direct loopback connection
The server SHALL support a direct connection transport that establishes the Remote Execution command channel **without** UDP multicast discovery. The transport SHALL open the local TCP command listen socket, then send an `open_connection` message with the `dest` field omitted (and `source` set to the session's stable node id) as **unicast UDP** to the configured RE bind host and multicast port, supplying the server's `command_ip`/`command_port` as payload. It SHALL re-send the `open_connection` message on a bounded retry schedule until the editor opens the TCP back-connection or the attempt budget is exhausted. Once the command channel is open, the server SHALL send `command` messages with the `dest` field omitted, and SHALL NOT require the editor's node id at any point.

#### Scenario: Direct connect on localhost
- **WHEN** the connection mode resolves to a direct attempt and a UE5 editor with Remote Execution enabled is running on the configured host with its RE bind address set to `127.0.0.1` or `0.0.0.0`
- **THEN** the editor SHALL open a TCP connection back to the server's command endpoint, the server SHALL accept it, transition to `CONNECTED`, and subsequent tool commands SHALL execute successfully — with no multicast traffic and no `pong` exchanged

#### Scenario: Direct connect when editor is not reachable
- **WHEN** a direct attempt sends `open_connection` and no TCP back-connection arrives within the retry budget
- **THEN** the attempt SHALL fail and report a clear error, leaving the connection in a non-`CONNECTED` state for the reconnect task to retry (or to fall back per the connection mode)

### Requirement: Connection mode selection with discovery fallback
The server SHALL expose a `UE_CONNECT_MODE` setting with values `auto` (default), `direct`, and `discovery`. In `auto` mode the server SHALL attempt the direct loopback transport first and fall back to multicast discovery if the direct attempt does not establish a command channel. `direct` SHALL use only the direct transport; `discovery` SHALL use only the multicast discovery transport.

#### Scenario: Auto mode falls back to discovery
- **WHEN** `UE_CONNECT_MODE` is `auto` and the direct loopback attempt fails (e.g. the editor's RE bind address is a real network adapter, so unicast to the configured host misses it)
- **THEN** the server SHALL then attempt multicast discovery before reporting the connection attempt as failed

#### Scenario: Forced discovery mode
- **WHEN** `UE_CONNECT_MODE` is `discovery`
- **THEN** the server SHALL use only the multicast discovery transport, preserving the prior behavior for cross-machine setups

### Requirement: Command channel read timeout
The TCP command channel SHALL apply a configurable receive timeout (`UE_COMMAND_RECV_TIMEOUT`, with a generous default) so that a busy or hung editor does not block a tool call indefinitely. A read timeout SHALL be treated as a connection fault: `execute()` SHALL return a structured connection error and transition the connection to `RECONNECTING` so the background task re-establishes the channel.

#### Scenario: Editor stops responding mid-command
- **WHEN** a `command` is sent and no `command_result` is received within `UE_COMMAND_RECV_TIMEOUT`
- **THEN** the call SHALL return `{"ok": false, "error": "UE5 editor not connected. Ensure the editor is running with Remote Execution enabled."}` rather than blocking, and the connection state SHALL transition to `RECONNECTING`

#### Scenario: Long-running command within the timeout
- **WHEN** a `command` legitimately takes time but completes before `UE_COMMAND_RECV_TIMEOUT`
- **THEN** the result SHALL be returned normally and the connection SHALL remain `CONNECTED`
