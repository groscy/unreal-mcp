## 1. Extension probe infrastructure (inert on its own)

- [x] 1.1 Add `UE_EDITOR_EXTENSIONS` config parsed as comma-separated `role=ClassName` pairs (roles: `blueprint`, `widget`; default `blueprint=BFEditorExtensions,widget=BFWidgetExtensions`), ignoring malformed entries and unknown roles without failing startup
- [x] 1.2 Implement a per-connection probe that checks `hasattr(unreal, "<name>")` for each configured class in a single Python snippet, returning the set of available roles
- [x] 1.3 Cache the probe result per connection epoch and re-run it on reconnect, replacing any prior result
- [x] 1.4 Treat a failed, disconnected, or malformed probe as "all roles unavailable" without failing startup or surfacing the error to the client
- [x] 1.5 Add a tool-level mechanism to declare a required extension role; leave every existing tool declaring none so `list_tools` output is unchanged
- [x] 1.6 Unit tests (mocked connection): role present, absent, config override, malformed config, probe failure, and refresh-on-reconnect

## 2. Capability-gated registration

- [x] 2.1 Filter `list_tools` to omit tools whose declared role is unavailable
- [x] 2.2 Return a structured error naming the missing class and its role when a hidden tool is called anyway, rather than raising
- [x] 2.3 Declare the `widget` role on `create_widget_layout` and `add_property_binding`
- [x] 2.4 Declare the `blueprint` role on `add_component`
- [x] 2.5 Unit tests: dependent tools advertised when the role is available, omitted when absent, non-dependent tools always advertised, and calling a hidden tool returns a structured error

## 3. Resolve the duplicate registrations

- [x] 3.1 Remove the dead pure-Python `add_component` registration, leaving the extension-backed registration as the only one
- [x] 3.2 Delete the unreachable pure-Python `add_component` implementation (`blueprints.py`) — it cannot succeed on UE 5.7 and its only reachable outcome is an error string
- [x] 3.3 Collapse the two `set_variable_default` registrations into a single registration with one schema, advertised unconditionally
- [x] 3.4 Implement call-time resolution for `set_variable_default`: use the extension when the `blueprint` role is available, else the pure-Python CDO path
- [x] 3.5 Update dispatch so neither name routes unconditionally to the `_cpp` variant
- [x] 3.6 Add a regression test asserting `list_tools` returns no duplicate tool names under every combination of role availability
- [x] 3.7 Unit tests for `set_variable_default` resolution order: role available, fallback on a C++-inherited variable, structured error on a Blueprint-defined variable, and missing asset path

## 4. Remove Battleforge domain logic

- [x] 4.1 Delete the `inspect_pie_state` tool registration and its `actors.py` implementation (**BREAKING** — no shim; Battleforge composes `set_pie_property` / `call_pie_function`)
- [x] 4.2 Remove or update tests referencing `inspect_pie_state`
- [x] 4.3 Parameterize the extension-backed snippets by the configured class name so no `BFEditorExtensions` / `BFWidgetExtensions` literal remains in tool bodies
- [x] 4.4 Grep `src/` for remaining `Battleforge` / `BFEditor` / `BFWidget` identifiers and confirm the only survivors are the `UE_EDITOR_EXTENSIONS` default values

## 5. Documentation

- [x] 5.1 Document `UE_EDITOR_EXTENSIONS` and its role syntax in the README env-var table
- [x] 5.2 Add a README section explaining extension-gated tools: why some tools appear only against an editor with an extension module built, and what the call-time error means
- [x] 5.3 Note the `inspect_pie_state` removal and its migration path
- [x] 5.4 Reconcile the README tool list with the gated surface, replacing the current undocumented five-tool gap with an explicit description of the gating

## 6. Verification

- [x] 6.1 Run the full unit suite; confirm no regressions
- [x] 6.2 Confirm generated snippets still compile and lint passes
- [ ] 6.3 (needs a live editor — not run) Manual check against a stock editor with no extension module: server starts, `list_tools` omits the gated tools and includes all others, and `set_variable_default` succeeds on a C++-inherited variable
- [ ] 6.4 (needs a live editor — not run) Manual check against a Battleforge editor with the module built: the gated tools appear and behave as before
