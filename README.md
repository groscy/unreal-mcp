# unreal-mcp

An MCP server that gives Claude (and any MCP client) full bidirectional access to a live Unreal Engine 5 editor session — no custom C++ plugins required.

## Prerequisites

- Python 3.11+
- [uv](https://docs.astral.sh/uv/) package manager
- Unreal Engine 5.x with the **Python Editor Script Plugin** enabled
- Remote Execution enabled in UE5 (see setup below)

## Installation

```bash
uv tool install unreal-mcp
```

Or to run directly without installing:

```bash
uvx unreal-mcp
```

## UE5 Remote Execution Setup

1. Open your UE5 project
2. Go to **Edit → Plugins** and enable the **Python Editor Script Plugin**
3. Go to **Edit → Project Settings → Plugins → Python**
4. Check **Enable Remote Execution**
5. Leave the default multicast settings unless you have network conflicts (default: `239.0.0.1:6766`)
6. Restart the editor

## Claude Desktop Configuration

Add this to your `claude_desktop_config.json` (located at `~/Library/Application Support/Claude/` on macOS or `%APPDATA%\Claude\` on Windows):

```json
{
  "mcpServers": {
    "unreal": {
      "command": "uvx",
      "args": ["unreal-mcp"]
    }
  }
}
```

Or if you installed with `uv tool install`:

```json
{
  "mcpServers": {
    "unreal": {
      "command": "unreal-mcp"
    }
  }
}
```

## Environment Variables

| Variable | Default | Description |
|---|---|---|
| `UE_MULTICAST_GROUP` | `239.0.0.1` | Remote Execution multicast group |
| `UE_MULTICAST_PORT` | `6766` | Remote Execution multicast port |
| `UE_COMMAND_PORT` | `6776` | Remote Execution TCP command port |
| `UE_CONNECT_TIMEOUT` | `3.0` | Seconds to wait for initial connection |

## Tools

### Connection
- `ping` — Check connection status and UE5 version

### Actor Management
- `list_actors` — List all actors in the current level
- `get_actor_properties` — Get editable properties of a named actor
- `place_actor` — Spawn an actor by class path at a transform
- `delete_actor` — Remove an actor from the level
- `set_actor_transform` — Update actor location/rotation/scale
- `set_actor_property` — Set a property on an actor or component

### Asset Management
- `list_assets` — List assets under a content browser path
- `find_asset` — Search for assets by name pattern
- `import_asset` — Import a file from disk into the content browser
- `save_asset` — Save a single asset
- `save_all_assets` — Save all dirty assets
- `duplicate_asset` — Duplicate an asset to a new path
- `delete_asset` — Delete an asset (with reference check)

### Blueprint Management
- `create_blueprint` — Create a new Blueprint with a given parent class
- `list_blueprints` — List Blueprint assets under a content path
- `compile_blueprint` — Compile a Blueprint and return errors/warnings
- `add_variable` — Add a variable to a Blueprint
- `add_function` — Add an empty function graph to a Blueprint
- `get_blueprint_info` — Get variables, functions, and components of a Blueprint
- `call_function` — Call a function on a level actor or Blueprint CDO

### Editor Control
- `play_in_editor` — Start a PIE session
- `stop_play` — Stop the current PIE session
- `open_level` — Open a level by content path
- `save_level` — Save the current level
- `run_console_command` — Execute an editor console command
- `get_world_settings` — Get World Settings properties
- `set_world_settings` — Set World Settings properties

### Python Execution
- `execute_python` — Execute arbitrary Python in the UE5 editor context (full trust, no restrictions)

## MCP Resources

- `unreal://level/hierarchy` — Live actor tree of the current level
- `unreal://content/tree` — Live content browser folder/asset tree
- `unreal://world/settings` — Live World Settings properties

Resources always reflect live editor state (fetched on every read, never cached).

## License

MIT
