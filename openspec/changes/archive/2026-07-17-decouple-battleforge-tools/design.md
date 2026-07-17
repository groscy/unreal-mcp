## Context

`unreal-mcp` ships to PyPI as a general-purpose UE5 MCP server, but carries tools bound to a private game project (Battleforge) whose C++ module lives outside this repo. There is no seam between "engine capability" and "project capability", and the absence of that seam has already produced a defect: 44 tool registrations under 42 unique names, with two tools registered twice and their pure-Python implementations shadowed into dead code by the dispatch table (`server.py:608`).

Two constraints shape the design:

1. **UE 5.7 Python API limits are real and asymmetric.** `SimpleConstructionScript` is not exposed, so `add_component` genuinely cannot work without C++. But the CDO *is* reachable, so `set_variable_default` works for variables inherited from C++ parents and fails only for Blueprint-defined ones. The two tools look identical in the registration table and are not identical underneath.
2. **Extension availability is a property of the connected editor, not of the installation.** The same `unreal-mcp` install can be pointed at a Battleforge editor and then at a stock one. Anything decided at import time will be wrong half the time.

The MCP protocol permits `list_tools` to return a different set per connection, which makes capability-dependent registration viable rather than merely desirable.

## Goals / Non-Goals

**Goals:**

- No tool is advertised that cannot run against the connected editor.
- Each tool name is registered exactly once; no dead registrations, no undefined client-side precedence.
- No Battleforge domain knowledge is hardcoded in the public server's tool surface.
- Battleforge keeps working with no configuration change when its C++ module is built.

**Non-Goals:**

- Publishing a separate `unreal-mcp-battleforge` distribution. The seam makes it unnecessary today.
- Making `add_component` work without C++. That is an engine limitation.
- Backfilling specs for the other unspecced tools (`add_event_dispatcher`, the UMG and runtime-verification families). Tracked separately.

## Decisions

### Gate registration on a runtime probe, not on configuration or install-time flags

The server probes the connected editor once per connection for the classes named in `UE_EDITOR_EXTENSIONS` (default `BFEditorExtensions,BFWidgetExtensions`) by checking `hasattr(unreal, "<name>")` — the same check the tool bodies already perform inline today (`umg.py:152`, `blueprints.py:476`). Tools declare which extension classes they need; `list_tools` filters on the recorded result.

*Alternatives considered.* **An env var like `UE_ENABLE_BF_TOOLS=1`** — rejected: it makes the user restate something the editor already knows, and it will be set wrong when the same install is pointed at a different project. **Registering everything and letting calls fail** — rejected: that is the current behavior and is exactly the complaint; a tool the model can see is a tool the model will try, and burning a round-trip to learn it cannot work is a real cost in an agent loop. **Probing per tool call** — rejected: it adds a round-trip to every call to answer a question whose answer cannot change within a connection.

The probe result is cached per connection and re-run on reconnect, because a reconnect may land on a different editor.

### Resolve the two duplicated tools differently, on the evidence

They are not the same problem and a uniform fix would be wrong:

- **`add_component`** — delete the dead pure-Python registration *and* its implementation (`blueprints.py:402`). That code cannot succeed on UE 5.7; its `EditorBlueprintLibrary` branch targets an API that does not exist there, and its only reachable outcome is an error string. Keeping it as a "fallback" would mean advertising a tool whose fallback is a guaranteed failure. The tool becomes extension-only and is hidden without the extension.
- **`set_variable_default`** — keep one registration, select the implementation at call time: extension when present, CDO path otherwise. The fallback covers a genuinely useful subset (C++-inherited variables) and degrades to a structured, actionable error for Blueprint-defined ones.

*Alternative considered.* **Delete both dead implementations for symmetry** — rejected: it would discard the working CDO path and leave PyPI users with no way to set defaults at all. Symmetry is not a reason to remove working code.

### Configure extensions by role, not as a flat list of class names

**Revised during implementation.** This decision originally said `UE_EDITOR_EXTENSIONS` would be a flat comma-separated list of class names. Writing the code proved that wrong, so the contract is now `role=ClassName` pairs (`blueprint=BFEditorExtensions,widget=BFWidgetExtensions`), tools declare a *role*, and the configured class name is passed into the snippet.

The flat list could not work. A tool does not merely need *some* extension class to exist — it calls named methods on a specific one (`unreal.BFEditorExtensions.add_component_to_blueprint(...)`, `unreal.BFWidgetExtensions.create_widget_layout(...)`), and it must know which configured class backs Blueprints versus widgets. With a flat list, `UE_EDITOR_EXTENSIONS=AcmeEditorExtensions` would probe successfully and then still call `unreal.BFEditorExtensions.*`, and nothing would say which part Acme plays. The original spec's own override scenario was therefore unimplementable, and the class name would have stayed hardcoded in every snippet body — the exact coupling this change exists to remove.

Roles fix that: config maps role → class name, the probe resolves each role's class, and the snippet is parameterized by the resolved name. Pointing `blueprint=` at another class is then meaningful, provided that class implements the same methods. The method set is the real contract; the class name is configuration.

*Alternatives considered.* **Flat list with positional roles** (first entry is Blueprints, second is widgets) — rejected: it makes list ordering silently load-bearing. **Accept the coupling** and keep class names hardcoded, documenting that only Battleforge domain logic was removed — rejected: it concedes the change's main goal to avoid a small config format. **A general plugin/entry-point system** where extensions register their own tools — rejected as premature: there is one known extension, and roles cover the need at a fraction of the surface area.

### Remove `inspect_pie_state` rather than generalize it

It reads `PowerPool`, `WellsHeld`, hand/deck counts and base HP — game rules, not engine state. There is no generic version of it, and no probe can make it meaningful elsewhere. The generic `set_pie_property` and `call_pie_function` already provide live PIE access, so Battleforge can compose them.

*Alternative considered.* **Gate it behind the extension probe like the others** — rejected: the probe answers "does this editor have the C++ module?", not "is this the Battleforge game?" A Battleforge editor with the module present would still be the only place the tool means anything, which is domain coupling the seam is meant to remove.

## Risks / Trade-offs

- **A dynamic tool list can surprise clients that cache `list_tools`** → The set only changes across connections, not within one. Clients that re-list on connect see the correct set; MCP already expects per-connection tool lists.
- **Removing `inspect_pie_state` breaks Battleforge smoke tests that call it by name** → **BREAKING**, and the mitigation is honest documentation rather than a shim: the migration note in the spec points at composing `set_pie_property`/`call_pie_function`. A deprecation window is not worth it for a tool with one known caller who is also the repo owner.
- **The probe adds a round-trip to connection setup** → One `hasattr` check batched into a single Python snippet per connection, on a channel that already round-trips for `ping`. Negligible against the existing 15 s connect timeout.
- **Hiding tools makes "why is this tool missing?" a new support question** → The call-time error for a hidden tool names the missing extension class explicitly, so a client that calls it anyway gets a diagnosis rather than a silent absence. The README needs a short section explaining the gating.
- **`UE_EDITOR_EXTENSIONS` defaulting to Battleforge class names is still a trace of the coupling** → Accepted deliberately: it keeps Battleforge zero-config and is one string in a config default rather than a branch in tool logic. If a second extension consumer appears, revisit the entry-point design.

## Migration Plan

1. Land the probe and the declaration mechanism with all existing tools declaring no dependency — a no-op refactor; `list_tools` is unchanged.
2. Move the four extension-backed tools onto declared dependencies and delete the duplicate registrations. Verified by the no-duplicate-names regression test.
3. Delete `inspect_pie_state` and the dead `add_component` implementation.
4. Update the README: document the gating and the `UE_EDITOR_EXTENSIONS` variable; the five previously-omitted tools stay undocumented as public tools and are described instead as extension-gated.

Rollback: each step is independently revertible; step 1 is inert on its own, and steps 2–4 are confined to registration wiring plus deletions.

## Open Questions

- Should `list_tools` distinguish "hidden because no extension" from "does not exist" in some discoverable way — a resource, or a note in the server instructions? Deferred until the README gating section proves insufficient.
- If a future extension consumer appears, does `UE_EDITOR_EXTENSIONS` grow to a mapping of class → tool set, or is that the point at which the entry-point design earns its complexity?
