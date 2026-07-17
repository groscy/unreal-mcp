## ADDED Requirements

### Requirement: Add a component to a Blueprint

The server SHALL provide an `add_component` tool that adds a component to a Blueprint's Simple Construction Script by class name. Because UE 5.7 does not expose `SimpleConstructionScript` to the Python API, this tool SHALL be implemented only against an editor extension class and SHALL declare a dependency on it, so that it is advertised only when that extension is available.

#### Scenario: Component is added via the extension

- **WHEN** `add_component` is called with a valid Blueprint asset path, a resolvable component class, and a variable name, against an editor where the extension is available
- **THEN** the component is added to the Blueprint's component hierarchy under the given variable name
- **AND** the Blueprint is compiled and saved
- **AND** the tool returns a success result

#### Scenario: Component class cannot be resolved

- **WHEN** `add_component` is called with a component class name that resolves to no class
- **THEN** the tool returns a structured error naming the unresolved class
- **AND** the Blueprint is left unmodified

#### Scenario: Tool is unavailable on a stock editor

- **WHEN** the connected editor exposes no extension class
- **THEN** `add_component` is not advertised in `list_tools`

### Requirement: Set the default value of a Blueprint variable

The server SHALL provide a `set_variable_default` tool that sets the default value of an existing Blueprint variable. The tool SHALL be advertised unconditionally and SHALL resolve its implementation at call time: it SHALL use the editor extension when available, and otherwise SHALL fall back to setting the value on the Class Default Object via the Python API.

#### Scenario: Extension is available

- **WHEN** `set_variable_default` is called against an editor where the extension is available
- **THEN** the tool sets the value via the extension
- **AND** returns a success result

#### Scenario: Fallback sets a variable inherited from a C++ parent class

- **WHEN** `set_variable_default` is called with no extension available, for a variable inherited from a C++ parent class
- **THEN** the tool sets the value on the Class Default Object
- **AND** saves the asset
- **AND** returns a success result

#### Scenario: Fallback cannot set a Blueprint-defined variable

- **WHEN** `set_variable_default` is called with no extension available, for a variable defined in the Blueprint itself
- **THEN** the tool returns a structured error stating that Blueprint-defined variables are not accessible via the Python CDO on UE 5.7
- **AND** the error includes guidance to set the default in the Blueprint Class Defaults panel or to build the editor extension

#### Scenario: Blueprint asset does not exist

- **WHEN** `set_variable_default` is called with an asset path that resolves to no asset
- **THEN** the tool returns a structured error naming the missing asset path
