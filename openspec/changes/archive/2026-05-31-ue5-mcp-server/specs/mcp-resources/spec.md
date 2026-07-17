## ADDED Requirements

### Requirement: Level hierarchy resource
The server SHALL expose a read-only MCP resource at URI `unreal://level/hierarchy` that returns the complete actor tree of the currently open level as JSON.

#### Scenario: Resource read with open level
- **WHEN** an MCP client reads `unreal://level/hierarchy`
- **THEN** the server SHALL query the live editor state and return a JSON document containing a tree of all actors with their labels, classes, parent-child relationships, and world transforms

#### Scenario: No level open
- **WHEN** an MCP client reads `unreal://level/hierarchy` and no level is currently open
- **THEN** the server SHALL return an empty tree `{"actors": []}`

### Requirement: Asset tree resource
The server SHALL expose a read-only MCP resource at URI `unreal://content/tree` that returns the content browser folder and asset structure as JSON.

#### Scenario: Resource read successfully
- **WHEN** an MCP client reads `unreal://content/tree`
- **THEN** the server SHALL return a nested JSON tree of content browser folders, each containing a list of assets with name, path, and class

#### Scenario: Resource reflects live state
- **WHEN** an asset is added or deleted and the resource is subsequently read
- **THEN** the returned tree SHALL reflect the current content browser state, not a cached snapshot

### Requirement: World settings resource
The server SHALL expose a read-only MCP resource at URI `unreal://world/settings` that returns the current level's World Settings properties as a flat JSON dict.

#### Scenario: Resource read with open level
- **WHEN** an MCP client reads `unreal://world/settings`
- **THEN** the server SHALL return the live World Settings properties as a JSON dict including game mode, gravity, and other editable world properties

### Requirement: Resources reflect live editor state
All MCP resources SHALL fetch data from the UE5 editor on every read. Resources SHALL NOT cache data between reads.

#### Scenario: Data changes between reads
- **WHEN** editor state changes (actor added, asset imported, setting changed) and a resource is read again
- **THEN** the resource SHALL return the updated state, not the previously returned state

### Requirement: Resources use the unreal:// URI scheme
All server-provided MCP resources SHALL use the `unreal://` URI scheme. URIs SHALL be stable across editor sessions for the same logical resource.

#### Scenario: Resource URI is stable
- **WHEN** the MCP server restarts and reconnects to UE5
- **THEN** the resource URIs SHALL remain identical, allowing clients to bookmark or cache URIs (not data)
