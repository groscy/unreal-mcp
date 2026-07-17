## 1. Project Scaffold

- [x] 1.1 Create `src/unreal_mcp/` package with `__init__.py` and `py.typed`
- [x] 1.2 Write `pyproject.toml` with `mcp` dependency, `unreal-mcp` CLI entry point, and `uv` tooling config
- [x] 1.3 Create `tests/` directory with `conftest.py`
- [x] 1.4 Add `.github/workflows/ci.yml` running lint (`ruff`) and tests (`pytest`) on push
- [x] 1.5 Write `README.md` with prerequisites, installation, Claude Desktop config snippet, and UE5 Remote Execution setup instructions

## 2. Remote Execution Client

- [x] 2.1 Copy `remote_execution.py` from UE5 install into `src/unreal_mcp/` and add license header
- [x] 2.2 Implement `connection.py` — singleton `UEConnection` class wrapping Remote Execution with connect/disconnect/reconnect logic
- [x] 2.3 Implement `execute(code: str) -> dict` method that sends Python code and returns `{"ok": bool, "stdout": str, "result": any, "error": str | None}`
- [x] 2.4 Implement `ping()` method that queries the UE version string
- [x] 2.5 Write unit tests for connection error paths (no UE running, connection drop, reconnect)

## 3. MCP Server Entrypoint

- [x] 3.1 Create `server.py` with `mcp.Server` instance, startup/shutdown hooks, and `stdio` transport wiring
- [x] 3.2 Register the `ping` tool from `remote-connection` spec
- [x] 3.3 Wire all tool modules and resource modules into the server at import time
- [x] 3.4 Implement graceful error wrapping: uncaught exceptions in tool handlers return structured `{"ok": false, "error": ...}` instead of crashing the server

## 4. Actor Management Tools

- [x] 4.1 Implement `list_actors` tool — queries all actors in the current level with label, class, and transform
- [x] 4.2 Implement `get_actor_properties` tool — returns editable properties of a named actor as nested JSON
- [x] 4.3 Implement `place_actor` tool — spawns an actor by class path at a given transform
- [x] 4.4 Implement `delete_actor` tool — removes a named actor from the level
- [x] 4.5 Implement `set_actor_transform` tool — updates world-space location/rotation/scale, supporting partial updates
- [x] 4.6 Implement `set_actor_property` tool — sets a named property on an actor or component
- [x] 4.7 Write tests for each actor tool's Python snippet generation (no live UE required)

## 5. Asset Management Tools

- [x] 5.1 Implement `list_assets` tool — queries asset registry for assets under a content path with optional recursion and class filter
- [x] 5.2 Implement `find_asset` tool — searches asset registry by name substring or glob
- [x] 5.3 Implement `import_asset` tool — runs automated import task for a given disk path and content destination
- [x] 5.4 Implement `save_asset` tool — saves a single asset by content path
- [x] 5.5 Implement `save_all_assets` tool — saves all dirty assets and returns count
- [x] 5.6 Implement `duplicate_asset` tool — duplicates asset to a new content path
- [x] 5.7 Implement `delete_asset` tool — deletes asset after checking for references
- [x] 5.8 Write tests for each asset tool's snippet generation

## 6. Blueprint Management Tools

- [x] 6.1 Implement `create_blueprint` tool — creates a new Blueprint asset with a given parent class
- [x] 6.2 Implement `list_blueprints` tool — lists Blueprint assets under a content path
- [x] 6.3 Implement `compile_blueprint` tool — triggers compile and returns errors/warnings
- [x] 6.4 Implement `add_variable` tool — adds a typed variable to a Blueprint's property list
- [x] 6.5 Implement `add_function` tool — creates a new empty function graph in a Blueprint
- [x] 6.6 Implement `get_blueprint_info` tool — returns variables, functions, and component hierarchy
- [x] 6.7 Implement `call_function` tool — invokes a named function on a level actor or Blueprint CDO
- [x] 6.8 Write tests for each blueprint tool's snippet generation

## 7. Editor Control Tools

- [x] 7.1 Implement `play_in_editor` tool — starts PIE session with guard against double-start
- [x] 7.2 Implement `stop_play` tool — ends PIE session with guard against calling when not running
- [x] 7.3 Implement `open_level` tool — loads a level by content browser path
- [x] 7.4 Implement `save_level` tool — saves the current level, errors on unsaved-path levels
- [x] 7.5 Implement `run_console_command` tool — executes an editor console command and captures output
- [x] 7.6 Implement `get_world_settings` tool — returns World Settings actor properties as JSON
- [x] 7.7 Implement `set_world_settings` tool — sets named properties on World Settings with unknown-property guard
- [x] 7.8 Write tests for each editor control tool's snippet generation

## 8. Python Execution Tool

- [x] 8.1 Implement `execute_python` tool — forwards raw code string to Remote Execution, returns stdout + result
- [x] 8.2 Verify no filtering, validation, or restriction is applied to submitted code
- [x] 8.3 Verify exception tracebacks are captured and returned in the error response

## 9. MCP Resources

- [x] 9.1 Implement `unreal://level/hierarchy` resource — live actor tree fetch on every read
- [x] 9.2 Implement `unreal://content/tree` resource — live content browser folder+asset tree on every read
- [x] 9.3 Implement `unreal://world/settings` resource — live World Settings fetch on every read
- [x] 9.4 Verify resources return updated data after editor state changes (no caching)
- [x] 9.5 Register all three resources in `server.py` with correct URI and MIME type (`application/json`)

## 10. Integration & Release

- [x] 10.1 Manual end-to-end test: connect to live UE5 editor, exercise each tool category
- [x] 10.2 Verify `ping` returns UE version and connection state correctly
- [x] 10.3 Add example `claude_desktop_config.json` snippet to README
- [x] 10.4 Tag `v0.1.0` release and publish package to PyPI via GitHub Actions
