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
| `UE_EDITOR_EXTENSIONS` | `blueprint=BFEditorExtensions,widget=BFWidgetExtensions` | Comma-separated `role=ClassName` pairs naming the optional C++ editor-extension class behind each role (see [Extension-gated tools](#extension-gated-tools)). Known roles: `blueprint`, `widget` |

## Extension-gated tools

Most tools work against a stock UE5 editor with nothing but the Python Editor Script Plugin. A few cannot: UE 5.7 does not expose everything to Python (for example `SimpleConstructionScript`, which is why a Blueprint component cannot be added from Python at all), so those tools are implemented against a **C++ editor-extension class** that is not part of this repo.

Rather than advertise tools that cannot run, the server asks the connected editor which extension classes it exposes and **only lists the dependent tools when they are present**. Against a stock editor you simply will not see them — that is expected, not a fault. If a client calls one anyway, it returns a structured error naming the class it needs.

Extensions are configured by **role**, since each tool calls specific methods on a specific class:

| Role | Default class | Gated tools |
|---|---|---|
| `blueprint` | `BFEditorExtensions` | `add_component` |
| `widget` | `BFWidgetExtensions` | `create_widget_layout`, `add_property_binding` |

To use your own C++ module, expose a class implementing the same methods and point the role at it:

```bash
UE_EDITOR_EXTENSIONS="blueprint=MyEditorExtensions,widget=MyWidgetExtensions"
```

`set_variable_default` is **not** gated: it uses the extension when available (which can also reach Blueprint-defined variables) and otherwise falls back to the Class Default Object, which works for variables inherited from a C++ parent class.

## Tools

Tools marked **(extension)** appear only when the relevant editor extension is present, as described above.

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
- `add_event_dispatcher` — Add a multicast delegate (Event Dispatcher) to a Blueprint
- `set_variable_default` — Set the default value of an existing Blueprint variable. Uses the `blueprint` extension when available; otherwise falls back to the CDO, which reaches variables inherited from a C++ parent class but not Blueprint-defined ones
- `get_blueprint_info` — Get variables, functions, and components of a Blueprint
- `call_function` — Call a function on a level actor or Blueprint CDO
- `add_component` — **(extension: `blueprint`)** Add a component to a Blueprint's component hierarchy. Requires an extension because UE 5.7 does not expose `SimpleConstructionScript` to Python

### Widget Blueprints (UMG)
- `create_widget_blueprint` — Create a new Widget Blueprint asset (UserWidget subclass)
- `scaffold_widget` — Create a Widget Blueprint and add variables and function stubs in one call
- `create_widget_layout` — **(extension: `widget`)** Build a UMG widget hierarchy from a JSON layout descriptor
- `add_property_binding` — **(extension: `widget`)** Bind a widget property to a Blueprint function (e.g. `TextBlock.Text` → `GetLabelText`)

### Editor Control
- `play_in_editor` — Start a PIE session
- `stop_play` — Stop the current PIE session
- `open_level` — Open a level by content path
- `save_level` — Save the current level
- `run_console_command` — Execute an editor console command
- `get_world_settings` — Get World Settings properties
- `set_world_settings` — Set World Settings properties

### Runtime Verification (PIE)

These tools observe and drive a running Play-In-Editor session, so you can verify gameplay and UI state without leaving the editor. All except `take_screenshot` require an active PIE session.

- `take_screenshot` — Capture the active viewport to a PNG and return it as an image. Captures the in-game view (HUD included) during PIE, otherwise the editor viewport
- `list_viewport_widgets` — List top-level UserWidgets currently in the PIE viewport (class, in_viewport, visibility)
- `inspect_live_widgets` — Inspect live widget instances by class (e.g. `TextBlock`, `Image`), returning runtime text, color/opacity tint, and visibility — including binding-driven values
- `set_pie_property` — Set a property on a live PIE object to stage a scenario. `target` is `player0`/`player1`, `gamemode`, `gamestate`, or an actor label; `property_path` is dot-separated
- `call_pie_function` — Invoke a BlueprintCallable function on a live PIE object to drive gameplay. Same `target` forms as above

### Python Execution
- `execute_python` — Execute arbitrary Python in the UE5 editor context (full trust, no restrictions)

## MCP Resources

- `unreal://level/hierarchy` — Live actor tree of the current level
- `unreal://content/tree` — Live content browser folder/asset tree
- `unreal://world/settings` — Live World Settings properties

Resources always reflect live editor state (fetched on every read, never cached).

## Removed tools

**`inspect_pie_state`** (removed) read gameplay state specific to one private game project (power pools, card hands, base HP). That is game-domain logic rather than an engine capability, so it does not belong in a general-purpose UE5 server and could not be generalised.

Use the generic PIE tools instead: `set_pie_property` to stage state and `call_pie_function` to drive gameplay, both of which target `player0`/`player1`, `gamemode`, `gamestate`, or an actor label. A project-specific convenience wrapper belongs in that project, composed from these.

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
