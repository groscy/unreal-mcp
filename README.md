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

## Status Indicator Plugin (optional, recommended)

The `UnrealMCPStatus` C++ plugin (under `ue5-plugin/UnrealMCPStatus/`) adds a live status label to the UE5 editor toolbar — **Disconnected** (grey), **Connecting** (yellow), **Connected** (green), or **Stopped** (red) — driven by a dedicated TCP heartbeat channel that is independent of Remote Execution. Because it does not rely on the command channel, it correctly shows **Stopped** the moment the MCP server exits or crashes.

To install:

1. Copy `ue5-plugin/UnrealMCPStatus/` into your project's `Plugins/` directory:
   ```
   <YourProject>/Plugins/UnrealMCPStatus/
   ```
2. Add the plugin to your `.uproject` file's `Plugins` array:
   ```json
   { "Name": "UnrealMCPStatus", "Enabled": true }
   ```
3. Right-click the `.uproject` and choose **Generate Visual Studio project files** (or run `GenerateProjectFiles`).
4. Rebuild the editor target (the plugin compiles against Engine modules only — `Sockets`, `Networking`, `Json`, `Slate`, `SlateCore`, `ToolMenus`, `LevelEditor`).
5. Launch the editor — the status label appears in the level editor toolbar automatically. No Python provisioning step is required.

> The legacy Python toolbar provisioning (`provisioning.py` / `unreal_mcp_status.py`) still works for projects without the C++ plugin, but is deprecated and will be removed in a future release.

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

## Example

Below is a real conversation with Claude Desktop after connecting unreal-mcp to the Battleforge project (UE 5.7). Claude has full read/write access to the live editor session.

---

**User:** What's in the level right now? Give me a quick summary.

**Claude:** The level contains 65 actors. The main categories are:

- **Lights** — 1 directional light (main sun), 4 point lights, 2 sky lights
- **Geometry** — 38 static mesh actors (terrain pieces, buildings, props)
- **Gameplay** — `BP_TopDownGameMode`, `BP_PlayerStart`, 6 patrol-path spline actors
- **Post-process** — 1 post-process volume covering the whole world
- **Utility** — `WorldSettings`, `SkyAtmosphere`, `VolumetricCloud`, `ExponentialHeightFog`

---

**User:** The scene looks too dark. Bump the directional light intensity to 8 and make the sky light twice as bright.

**Claude:** *(calls `list_actors`, identifies `DirectionalLight` and `SkyLight`, then calls `set_actor_property` twice)*

Done. Set `DirectionalLight` → `LightComponent.Intensity` to **8.0** and `SkyLight` → `LightComponent.Intensity` to **2.0**. The changes are live in the viewport — you may want to do a quick PIE run to see how it feels in-game.

---

**User:** Create a Blueprint called BP_Torch that extends Actor, add a float variable called BrightnessScale defaulting to 1.0, then compile it.

**Claude:** *(calls `create_blueprint`, `add_variable`, `compile_blueprint`)*

Created `/Game/Blueprints/BP_Torch` extending `Actor`. Added `BrightnessScale` (Float, default 1.0). Compiled cleanly — no errors or warnings.

---

**User:** Place 3 torches in a triangle around the player start, roughly 300 units out.

**Claude:** *(calls `get_actor_properties` on `BP_PlayerStart` to get its location `[1200, -400, 120]`, then calls `place_actor` three times)*

Placed:
- `BP_Torch_1` at [1500, -400, 120] (north)
- `BP_Torch_2` at [1050, -141, 120] (south-east)
- `BP_Torch_3` at [1050, -659, 120] (south-west)

All three are roughly 300 units from the player start in an equilateral triangle. Saved the level.

---

**User:** Something's wrong with the gravity — objects are floating. Check and fix it.

**Claude:** *(calls `get_world_settings`)*

World Settings shows `gravity_z` is set to **0.0** — that's why objects float. UE5's default is **-980.0** (cm/s²). Setting it back now.

*(calls `set_world_settings` with `{"gravity_z": -980.0}`)*

Fixed. Gravity is restored to -980.0.

---

## Environment Variables

| Variable | Default | Description |
|---|---|---|
| `UE_CONNECT_MODE` | `auto` | Connection strategy: `auto` (direct first, then discovery fallback), `direct` (loopback only), or `discovery` (multicast only) |
| `UE_CONNECT_HOST` | `127.0.0.1` | Host to send the unicast `open_connection` to in direct mode (override when the editor's RE bind address is a real NIC) |
| `UE_MULTICAST_BIND` | `127.0.0.1` | Adapter address for the multicast socket (must match UE's "Multicast Bind Address" setting when using discovery mode) |
| `UE_MULTICAST_GROUP` | `239.0.0.1` | Remote Execution multicast group |
| `UE_MULTICAST_PORT` | `6766` | Remote Execution multicast port |
| `UE_COMMAND_PORT` | `6776` | Remote Execution TCP command port |
| `UE_CONNECT_TIMEOUT` | `15.0` | Seconds to wait for a node during multicast discovery |
| `UE_COMMAND_RECV_TIMEOUT` | `30.0` | Read timeout (seconds) for the command channel; prevents a hung editor from blocking tool calls indefinitely |
| `UE_MCP_HEARTBEAT_PORT` | `6690` | TCP port of the `UnrealMCPStatus` plugin's heartbeat listener |
| `UE_MCP_HEARTBEAT_INTERVAL` | `5.0` | Seconds between heartbeat messages |

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

## Troubleshooting

**The server never connects on Windows (spins in "Connecting" forever).**
The default connection strategy (`UE_CONNECT_MODE=auto`) bypasses multicast entirely: it sends a unicast UDP packet to `127.0.0.1:6766`, which triggers the editor to open a TCP back-connection — no multicast socket is involved, so Windows Firewall and virtual adapters (Hyper-V / WSL2 / Docker / VPN) cannot block it.

If the direct path fails (e.g. UE's "Multicast Bind Address" is set to a real NIC rather than `127.0.0.1` / `0.0.0.0`), the server automatically falls back to multicast discovery. You can force one or the other with `UE_CONNECT_MODE=direct` or `UE_CONNECT_MODE=discovery`.

Cross-machine or non-default NIC setups: set `UE_CONNECT_HOST=<editor-NIC-IP>` to point the unicast directly at the right interface, or use `UE_CONNECT_MODE=discovery` with `UE_MULTICAST_BIND=<local-NIC-IP>`.

**The direct connect path works against the stock `PythonScriptPlugin` with its default settings — no UE5-side changes required.**

**The toolbar status stays "Disconnected" even though the server is running.**
The heartbeat ports must match on both sides. The Python server connects to the port set by `UE_MCP_HEARTBEAT_PORT` (default `6690`); the C++ plugin listens on the port set by the `mcp.HeartbeatPort` console variable (default `6690`). If you change one, change the other to match.

**The status shows "Port in use".**
Another process (or a second editor instance) already bound the heartbeat port. Close the other listener or set both `mcp.HeartbeatPort` (C++) and `UE_MCP_HEARTBEAT_PORT` (Python) to a free port.

**The status takes a while to show "Stopped" after a crash.**
On a clean shutdown the server sends an explicit `stopped` event and the widget updates within a second. If the server is killed abruptly *and* the TCP socket close is not detected immediately, the widget falls back to "Stopped" after a heartbeat timeout of **15 seconds** (3 × the 5-second interval, configurable via `mcp.HeartbeatIntervalSeconds` and `mcp.HeartbeatTimeoutBeats`).

## License

MIT
