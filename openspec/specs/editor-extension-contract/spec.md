## ADDED Requirements

### Requirement: Configure editor extensions by role

An extension-backed tool does not merely need *some* extension class to exist — it calls specific methods on a specific class, and it must know which configured class plays which part. The server SHALL therefore map an extension **role** to a **class name**.

The server SHALL define the roles it understands (`blueprint` and `widget`) and SHALL resolve each role to a class name via the `UE_EDITOR_EXTENSIONS` environment variable, formatted as comma-separated `role=ClassName` pairs, defaulting to `blueprint=BFEditorExtensions,widget=BFWidgetExtensions`. The server SHALL NOT hardcode any project-specific class name as a non-overridable constant.

A class named in configuration is expected to expose the method set the tools for that role call. Pointing a role at a different class means supplying a class that implements the same methods.

#### Scenario: Default configuration

- **WHEN** `UE_EDITOR_EXTENSIONS` is not set
- **THEN** the `blueprint` role resolves to `BFEditorExtensions`
- **AND** the `widget` role resolves to `BFWidgetExtensions`

#### Scenario: A role is pointed at a different class

- **WHEN** `UE_EDITOR_EXTENSIONS` is set to `blueprint=AcmeEditorExtensions`
- **THEN** the server probes for `AcmeEditorExtensions` and not for `BFEditorExtensions`
- **AND** tools in the `blueprint` role call methods on `AcmeEditorExtensions`
- **AND** the `widget` role, being unmentioned, retains its default class name

#### Scenario: Malformed configuration entry

- **WHEN** `UE_EDITOR_EXTENSIONS` contains an entry that is not a `role=ClassName` pair, or names a role the server does not understand
- **THEN** the server SHALL ignore that entry and retain the default for any role it did not validly override
- **AND** SHALL NOT fail startup

### Requirement: Probe the connected editor for configured extension classes

The server SHALL detect, per connection, which of the configured extension classes the connected editor's `unreal` module exposes, and SHALL treat a role as available only when its configured class is present.

#### Scenario: Extension class is present in the editor

- **WHEN** the server probes a connected editor whose `unreal` module exposes the class configured for the `blueprint` role
- **THEN** the server records the `blueprint` role as available for that connection

#### Scenario: Extension class is absent from the editor

- **WHEN** the server probes a connected editor that exposes none of the configured classes
- **THEN** the server records every role as unavailable
- **AND** the server continues to start normally and serve all non-extension tools

#### Scenario: Probe cannot be completed

- **WHEN** the probe fails because the editor is disconnected, unresponsive, or returns a malformed response
- **THEN** the server SHALL treat every role as unavailable
- **AND** SHALL NOT fail startup or raise the error to the client

#### Scenario: Probe result is refreshed on reconnect

- **WHEN** the connection to the editor is re-established after a disconnect
- **THEN** the server SHALL re-run the probe against the newly connected editor
- **AND** SHALL replace any previously recorded availability result

### Requirement: Register extension-dependent tools only when their role is available

A tool MAY declare a dependency on an extension role. The server SHALL advertise such a tool in `list_tools` only when that role is available. Tools with no declared role SHALL always be advertised.

#### Scenario: Dependent tool is advertised when its role is available

- **WHEN** a client calls `list_tools` against an editor exposing the `widget` role's configured class
- **THEN** the response includes `create_widget_layout` and `add_property_binding`

#### Scenario: Dependent tool is hidden when its role is unavailable

- **WHEN** a client calls `list_tools` against a stock editor with no extension module built
- **THEN** the response does not include `create_widget_layout`, `add_property_binding`, or `add_component`
- **AND** the response still includes every tool that declares no role

#### Scenario: Hidden tool is called anyway

- **WHEN** a client calls `add_component` against an editor where the `blueprint` role is unavailable
- **THEN** the server SHALL return a structured error naming the missing class and the role it backs
- **AND** SHALL NOT raise an unhandled exception

### Requirement: Each tool name is registered exactly once

The server SHALL register each tool name at most once. `list_tools` SHALL NOT return two entries sharing a name, under any combination of role availability.

#### Scenario: No duplicate tool names are advertised

- **WHEN** a client calls `list_tools` with any set of roles available
- **THEN** every returned tool name is unique within the response

#### Scenario: A tool with an extension-backed and a fallback implementation

- **WHEN** a tool such as `set_variable_default` has both an extension-backed and a pure-Python implementation
- **THEN** the server SHALL advertise it as a single tool with a single schema
- **AND** SHALL select the implementation at call time rather than by registering two tools
