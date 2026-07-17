## ADDED Requirements

### Requirement: Start Play-in-Editor
The server SHALL expose a `play_in_editor` tool that starts a PIE session in the currently open level.

#### Scenario: PIE started successfully
- **WHEN** `play_in_editor` is called and no PIE session is active
- **THEN** PIE SHALL start and the tool SHALL return `{"ok": true}`

#### Scenario: PIE already running
- **WHEN** `play_in_editor` is called while a PIE session is already active
- **THEN** it SHALL return `{"ok": false, "error": "PIE session is already running"}`

### Requirement: Stop Play-in-Editor
The server SHALL expose a `stop_play` tool that ends the current PIE session.

#### Scenario: PIE stopped successfully
- **WHEN** `stop_play` is called while a PIE session is active
- **THEN** PIE SHALL end and the tool SHALL return `{"ok": true}`

#### Scenario: No PIE session active
- **WHEN** `stop_play` is called and no PIE session is running
- **THEN** it SHALL return `{"ok": false, "error": "No PIE session is currently running"}`

### Requirement: Open a level
The server SHALL expose an `open_level` tool that loads a level asset by its content browser path, replacing the currently open level.

#### Scenario: Level opened successfully
- **WHEN** `open_level` is called with a valid level asset path
- **THEN** the level SHALL be loaded in the editor and the tool SHALL return `{"ok": true, "level_path": "<path>"}`

#### Scenario: Level asset not found
- **WHEN** `open_level` is called with a path that does not resolve to a level asset
- **THEN** it SHALL return `{"ok": false, "error": "Level not found: '<path>'"}`

### Requirement: Save the current level
The server SHALL expose a `save_level` tool that saves the currently open level to disk.

#### Scenario: Level saved
- **WHEN** `save_level` is called with an open, named level
- **THEN** the level SHALL be saved and the tool SHALL return `{"ok": true}`

#### Scenario: Unsaved new level
- **WHEN** `save_level` is called on a level that has never been saved (no file path yet)
- **THEN** it SHALL return `{"ok": false, "error": "Level has no save path. Use save_as or save the level manually first."}`

### Requirement: Run a console command
The server SHALL expose a `run_console_command` tool that executes an arbitrary editor console command string and returns any output.

#### Scenario: Console command executed
- **WHEN** `run_console_command` is called with a valid command string
- **THEN** the command SHALL be executed in the editor context and the tool SHALL return `{"ok": true, "output": "<console output if any>"}`

### Requirement: Get world settings
The server SHALL expose a `get_world_settings` tool that returns the properties of the current level's World Settings actor as a JSON dict.

#### Scenario: World settings returned
- **WHEN** `get_world_settings` is called with an open level
- **THEN** it SHALL return `{"ok": true, "settings": {"game_mode": "...", "gravity_z": ..., ...}}`

### Requirement: Set world settings
The server SHALL expose a `set_world_settings` tool that sets one or more named properties on the World Settings actor.

#### Scenario: Settings updated
- **WHEN** `set_world_settings` is called with a dict of property names and values
- **THEN** each property SHALL be updated and the tool SHALL return `{"ok": true, "updated": ["<property_name>", ...]}`

#### Scenario: Unknown property name
- **WHEN** `set_world_settings` includes a property name that does not exist on World Settings
- **THEN** it SHALL return `{"ok": false, "error": "Unknown world setting property: '<name>'"}`
