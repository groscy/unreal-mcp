## ADDED Requirements

### Requirement: C++ plugin displays MCP status in the UE5 editor status bar
The `UnrealMCPStatus` UE5 C++ plugin SHALL register a Slate widget in the main editor toolbar (PlayToolBar section, same location as the existing Python-based status label) that shows the current MCP server state. The widget SHALL be visible at all times while the editor is open, with no additional user configuration.

#### Scenario: Editor starts with no MCP server connected
- **WHEN** the UE5 editor starts and the UnrealMCPStatus plugin is enabled in the project
- **THEN** the toolbar SHALL display "MCP: Disconnected" in grey within 3 seconds of editor startup

#### Scenario: Plugin enabled for the first time
- **WHEN** a user adds the plugin to their .uproject and opens the editor
- **THEN** the status widget SHALL appear automatically without any Python provisioning step or UE5 restart beyond the initial plugin enable

### Requirement: Status widget reflects four distinct states
The status widget SHALL display one of four states with distinguishable visual presentation (text label + color):

- **Disconnected** (grey): No Python server has connected since the editor started
- **Connecting** (yellow): A `connected` event was received but fewer than 2 heartbeats have been received yet — transitional state, visible for at most 6 seconds
- **Connected** (green): Heartbeats are arriving within the expected interval
- **Stopped** (red): The server sent a `stopped` event OR heartbeats have timed out OR the TCP socket was closed unexpectedly

#### Scenario: Python server connects
- **WHEN** the plugin receives a `{"event":"connected"}` message over the heartbeat channel
- **THEN** the widget SHALL transition from Disconnected to Connecting, then to Connected after the first heartbeat

#### Scenario: Python server sends stopped event
- **WHEN** the plugin receives a `{"event":"stopped"}` message
- **THEN** the widget SHALL immediately display "MCP: Stopped" in red

#### Scenario: Heartbeat timeout
- **WHEN** no heartbeat is received for more than `3 × interval` seconds (default 15 s)
- **THEN** the widget SHALL transition to the Stopped state in red

### Requirement: Status widget shows a tooltip with actionable information
The toolbar widget SHALL display a tooltip on hover that describes the current state and, where applicable, a hint for what the user can do.

#### Scenario: Disconnected state tooltip
- **WHEN** the user hovers over the widget in the Disconnected state
- **THEN** the tooltip SHALL read: "MCP server has not connected. Start the MCP server via your MCP client configuration."

#### Scenario: Connected state tooltip
- **WHEN** the user hovers over the widget in the Connected state
- **THEN** the tooltip SHALL read: "MCP server is connected (PID: <pid>)" where `<pid>` is the value from the last `connected` event

#### Scenario: Stopped state tooltip
- **WHEN** the user hovers over the widget in the Stopped state
- **THEN** the tooltip SHALL read: "MCP server has stopped or is unreachable. Restart your MCP client."

### Requirement: Plugin is source-distributed and compiles without modification
The `UnrealMCPStatus` plugin SHALL be distributed as C++ source code in the `ue5-plugin/UnrealMCPStatus/` directory of the `unreal-mcp` repository. It SHALL compile against UE5.3 or later without changes to Engine source.

#### Scenario: User adds plugin to project
- **WHEN** the user copies `ue5-plugin/UnrealMCPStatus/` to their project's `Plugins/` directory, adds it to `.uproject`, and runs "Generate Project Files"
- **THEN** the plugin SHALL compile as part of the editor build with no additional dependencies beyond Engine modules (Sockets, Slate, SlateCore, ToolMenus, LevelEditor)

### Requirement: Python-based status provisioning is deprecated
The Python `unreal_mcp_status.py` provisioning and `push_ue_status()` calls SHALL remain functional for projects that have not yet installed the C++ plugin, but SHALL be marked as deprecated in code comments. New projects SHALL use the C++ plugin exclusively.

#### Scenario: Project with C++ plugin installed
- **WHEN** both the C++ plugin and the Python `unreal_mcp_status.py` module are present
- **THEN** both may coexist without conflict; the C++ plugin's widget takes priority in the toolbar (it registers at a different named slot)

#### Scenario: Project without C++ plugin
- **WHEN** the C++ plugin is not installed
- **THEN** the Python provisioning path SHALL continue to work as before
