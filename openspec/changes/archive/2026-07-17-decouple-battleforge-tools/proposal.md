## Why

`unreal-mcp` is published to PyPI as a general-purpose UE5 MCP server, but five of its 42 tools are wired to **Battleforge**, a private game project whose C++ module is not in this repo. Anyone who runs `uv tool install unreal-mcp` gets tools that cannot work:

- `add_component`, `set_variable_default`, `create_widget_layout`, `add_property_binding` fail with `"BFEditorExtensions not available — build BattleforgeEditor first."`
- `inspect_pie_state` reads Battleforge domain state (`PowerPool`, `WellsHeld`, hand/deck counts, base HP) that exists in no other project.

The coupling has already produced a concrete defect. `server.py` makes **44 tool registrations under 42 unique names**: `add_component` and `set_variable_default` are each registered twice with different descriptions and schemas (`server.py:267`/`:294` and `:280`/`:307`) — once as a pure-Python tool, once as a C++-backed one. Dispatch (`server.py:608`) routes both names unconditionally to the `_cpp` variants, so the pure-Python implementations (`blueprints.py:402`, `blueprints.py:293`) are unreachable dead code, and MCP clients are handed duplicate tool names with undefined precedence. The duplicate registration is not a typo; it is what happens when project-specific tools are grafted onto a general server with no seam between them.

Inspecting the shadowed implementations shows the fix is **not uniform**, which is why this needs a design rather than a one-line deletion:

- Pure-Python `add_component` (`blueprints.py:402`) **cannot work on UE 5.7 at all** — `SimpleConstructionScript` is not exposed to Python, so the code path always terminates in an informative error. Its `EditorBlueprintLibrary` branch is speculative future-proofing for an API that does not exist in 5.7. A fallback here buys nothing.
- Pure-Python `set_variable_default` (`blueprints.py:293`) **partially works** — it sets defaults on variables inherited from C++ parent classes via the CDO, and only fails for Blueprint-defined variables. A fallback here has real value for PyPI users.

Now is the right time: the README was just corrected to document 37 of 42 tools, deliberately omitting these five. That gap is currently an undocumented convention held in one person's head, which is a poor substitute for a seam in the code.

## What Changes

- **New optional editor-extension contract.** The server probes the connected editor for an extension class and registers the tools that depend on it **only when it is present**. The probe target is configurable (env var), defaulting to the known `BFEditorExtensions`/`BFWidgetExtensions` names. PyPI users stop seeing tools that cannot run; Battleforge users keep them automatically with no configuration.
- **Tool registration becomes capability-dependent** rather than static. `list_tools` reflects what the connected editor can actually do.
- **Duplicate registrations removed**, resolved per-tool on the evidence above:
  - `add_component` — drop the dead pure-Python registration and implementation; the tool is extension-backed only, and is advertised only when the extension is present.
  - `set_variable_default` — keep a single registration that prefers the extension when available and **falls back to the pure-Python CDO path** otherwise, with the existing Blueprint-defined-variable limitation surfaced as a structured error.
- **`inspect_pie_state` removed from the public server.** It is Battleforge domain logic, not an engine capability, and cannot be generalized. The generic `set_pie_property` and `call_pie_function` tools already cover live PIE access; Battleforge composes them or keeps a private wrapper. **BREAKING** for Battleforge workflows that call it by name.
- **No Battleforge identifiers remain in the public server's tool surface** — the `BFEditorExtensions` name survives only as a configurable default value, not as hardcoded domain knowledge.

## Capabilities

### New Capabilities

- `editor-extension-contract`: Defines the optional C++ editor-extension seam — how the server probes a connected editor for extension classes, how tools declare a dependency on one, and how registration is gated on the probe result. Covers the configurable probe target and the behavior when an extension is absent.

### Modified Capabilities

- `blueprint-management`: Adds requirements for `add_component` and `set_variable_default`, which are currently implemented but entirely unspecced. Fixes the duplicate-registration defect by requiring each tool name to be registered exactly once, and defines `set_variable_default`'s extension-preferred / Python-fallback resolution order.

## Impact

- Modified files: `src/unreal_mcp/server.py` (registration + dispatch), `src/unreal_mcp/tools/blueprints.py` (remove dead `add_component`, keep `set_variable_default` fallback), `src/unreal_mcp/tools/umg.py` (extension-gated tools), `src/unreal_mcp/tools/actors.py` (remove `inspect_pie_state`), `README.md`
- New tests: extension-probe detection (mocked), conditional registration with/without the extension, `set_variable_default` fallback order, and a regression test asserting **no duplicate tool names** in `list_tools`
- **No UE5-side changes** to the stock `PythonScriptPlugin`; the `UnrealMCPStatus` plugin is unaffected
- **No protocol changes**; the wire format and connection path are untouched
- Battleforge impact: `add_component`, `create_widget_layout`, `add_property_binding`, `set_variable_default` keep working unchanged when the C++ module is built. `inspect_pie_state` is removed and must be replaced by composing generic PIE tools.

## Non-Goals

- **Backfilling specs for the other unspecced tools.** Investigation found that `add_event_dispatcher`, the UMG family (`create_widget_blueprint`, `scaffold_widget`), and the entire runtime-verification family (`take_screenshot`, `inspect_live_widgets`, `list_viewport_widgets`, `set_pie_property`, `call_pie_function`) were added to the code with no spec coverage at all. Only the specs this change actually touches are written here; the broader drift is tracked separately.
- **Publishing a separate `unreal-mcp-battleforge` package.** The extension-contract seam makes a second distribution unnecessary for now; revisit if Battleforge-specific tools multiply.
- **Making `add_component` work without the C++ module.** UE 5.7 does not expose `SimpleConstructionScript` to Python; this is an engine limitation, not something this change can route around.
