## ADDED Requirements

### Requirement: List assets in a content path
The server SHALL expose a `list_assets` tool that returns all assets under a given content browser path, with optional recursive traversal and class filtering.

#### Scenario: List assets at path
- **WHEN** `list_assets` is called with a valid content path (e.g. `/Game/Meshes`)
- **THEN** it SHALL return `{"ok": true, "assets": [{"name": "...", "path": "...", "class": "..."}, ...]}`

#### Scenario: Path does not exist
- **WHEN** `list_assets` is called with a path that has no assets and no subdirectories
- **THEN** it SHALL return `{"ok": true, "assets": []}`

### Requirement: Find assets by name pattern
The server SHALL expose a `find_asset` tool that searches the asset registry for assets whose name matches a given substring or glob pattern.

#### Scenario: Assets found matching pattern
- **WHEN** `find_asset` is called with a search pattern
- **THEN** it SHALL return `{"ok": true, "assets": [...]}` with all matching assets

#### Scenario: No assets match pattern
- **WHEN** `find_asset` is called with a pattern that matches nothing
- **THEN** it SHALL return `{"ok": true, "assets": []}`

### Requirement: Import an asset from disk
The server SHALL expose an `import_asset` tool that imports a file from an absolute disk path into a specified content browser destination path.

#### Scenario: Successful import
- **WHEN** `import_asset` is called with a valid source file path and destination content path
- **THEN** the asset SHALL be imported and the tool SHALL return `{"ok": true, "asset_path": "<content path of imported asset>"}`

#### Scenario: Source file not found
- **WHEN** `import_asset` is called with a source path that does not exist on disk
- **THEN** it SHALL return `{"ok": false, "error": "Source file not found: '<path>'"}`

### Requirement: Save a specific asset
The server SHALL expose a `save_asset` tool that saves a single asset by its content browser path.

#### Scenario: Asset saved
- **WHEN** `save_asset` is called with a valid asset content path
- **THEN** the asset SHALL be saved to disk and the tool SHALL return `{"ok": true}`

#### Scenario: Asset path not found
- **WHEN** `save_asset` is called with a path that resolves to no asset
- **THEN** it SHALL return `{"ok": false, "error": "Asset not found: '<path>'"}`

### Requirement: Save all dirty assets
The server SHALL expose a `save_all_assets` tool that saves every modified asset in the project.

#### Scenario: All assets saved
- **WHEN** `save_all_assets` is called
- **THEN** all dirty assets SHALL be saved and the tool SHALL return `{"ok": true, "saved_count": <n>}`

### Requirement: Duplicate an asset
The server SHALL expose a `duplicate_asset` tool that creates a copy of an existing asset at a new content browser path.

#### Scenario: Asset duplicated
- **WHEN** `duplicate_asset` is called with a valid source path and a new destination path
- **THEN** a copy SHALL be created and the tool SHALL return `{"ok": true, "new_path": "<destination path>"}`

### Requirement: Delete an asset
The server SHALL expose a `delete_asset` tool that deletes an asset from the content browser by its path.

#### Scenario: Asset deleted
- **WHEN** `delete_asset` is called with a valid asset path
- **THEN** the asset SHALL be deleted and the tool SHALL return `{"ok": true}`

#### Scenario: Asset has references
- **WHEN** `delete_asset` is called on an asset that is referenced by other assets
- **THEN** it SHALL return `{"ok": false, "error": "Asset has references: [...]"}` listing the referencing assets
