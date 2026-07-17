## ADDED Requirements

### Requirement: UE5 editor displays MCP connection status in toolbar
The UE5 editor SHALL display a persistent toolbar label showing the current MCP server connection state. The label SHALL be visible in the main editor toolbar at all times while the editor is running.

#### Scenario: Editor starts with no MCP server running
- **WHEN** the UE5 editor starts and `init_unreal.py` has been configured
- **THEN** the toolbar SHALL display "MCP: Disconnected" in a neutral color (grey)

#### Scenario: Editor starts with MCP server already connected
- **WHEN** the MCP server was running before the editor loaded and the status module is already initialized
- **THEN** the toolbar SHALL display "MCP: Connected" in green after the first status push

### Requirement: Status label updates when MCP server connects
When the MCP server establishes a connection to the UE5 editor, the toolbar label SHALL update to reflect the connected state without requiring any user action.

#### Scenario: MCP server connects while editor is open
- **WHEN** the MCP server successfully completes its connection handshake with UE5
- **THEN** the server SHALL execute a status-push Python snippet in UE5 that updates the toolbar label to "MCP: Connected" within one second

#### Scenario: Status push fails silently
- **WHEN** the status-push Python snippet execution fails (e.g., module not yet loaded)
- **THEN** the MCP server SHALL log a warning and continue normally without raising an exception

### Requirement: Status label updates when MCP server disconnects
When the MCP server disconnects from the UE5 editor, it SHALL make a best-effort attempt to update the toolbar label to the disconnected state.

#### Scenario: MCP server disconnects cleanly
- **WHEN** the MCP server's `disconnect()` is called (e.g., on server shutdown)
- **THEN** the server SHALL attempt to execute a status-push Python snippet in UE5 that updates the label to "MCP: Disconnected" before closing the socket

#### Scenario: MCP server crashes or loses connection abruptly
- **WHEN** the connection is lost without a clean disconnect
- **THEN** the toolbar label MAY remain stale until the next explicit status push; no crash or error SHALL occur in UE5

### Requirement: UE5-side status module is auto-loaded at editor startup
A Python module (`unreal_mcp_status.py`) placed in the UE5 project's `Content/Python/` directory SHALL be imported automatically at editor startup via `init_unreal.py`, so the toolbar widget is available before the first MCP connection.

#### Scenario: Module loaded successfully at startup
- **WHEN** `init_unreal.py` contains `import unreal_mcp_status` and the editor starts
- **THEN** the toolbar entry SHALL be registered and visible in the default "disconnected" state

#### Scenario: Module fails to load (API unavailable)
- **WHEN** `unreal_mcp_status.py` fails to register the toolbar entry (e.g., ToolMenus API unavailable)
- **THEN** the import SHALL complete without raising an unhandled exception, and a warning SHALL be printed to the UE output log

### Requirement: MCP server provisions the UE5 status module on first connect
On the first successful connection, the MCP server SHALL ensure the `unreal_mcp_status.py` file and the `init_unreal.py` import line exist in the UE5 project's `Content/Python/` directory.

#### Scenario: Files do not exist yet
- **WHEN** the MCP server connects for the first time and `unreal_mcp_status.py` is absent from `Content/Python/`
- **THEN** the MCP server SHALL write `unreal_mcp_status.py` and append the import line to `init_unreal.py` (creating it if needed)

#### Scenario: Files already exist
- **WHEN** the MCP server connects and `unreal_mcp_status.py` already exists
- **THEN** the MCP server SHALL NOT overwrite the existing file, and SHALL NOT duplicate the import line in `init_unreal.py`

#### Scenario: Project Python path is unknown
- **WHEN** the MCP server cannot determine the UE5 project's `Content/Python/` path
- **THEN** provisioning SHALL be skipped, a warning SHALL be logged, and the connection SHALL continue normally
