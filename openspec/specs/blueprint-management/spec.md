## ADDED Requirements

### Requirement: Create a Blueprint class
The server SHALL expose a `create_blueprint` tool that creates a new Blueprint asset at a given content browser path with a specified parent class.

#### Scenario: Blueprint created with valid parent class
- **WHEN** `create_blueprint` is called with a content path and a valid parent class (e.g. `Actor`, `Pawn`, `Character`)
- **THEN** a new Blueprint asset SHALL be created and the tool SHALL return `{"ok": true, "asset_path": "<content path>"}`

#### Scenario: Invalid parent class
- **WHEN** `create_blueprint` is called with a parent class that cannot be resolved
- **THEN** it SHALL return `{"ok": false, "error": "Parent class '<class>' not found"}`

#### Scenario: Asset path already exists
- **WHEN** `create_blueprint` is called with a path that already contains an asset
- **THEN** it SHALL return `{"ok": false, "error": "Asset already exists at '<path>'"}`

### Requirement: List blueprints in a content path
The server SHALL expose a `list_blueprints` tool that returns all Blueprint assets under a given content browser path.

#### Scenario: Blueprints found
- **WHEN** `list_blueprints` is called with a content path containing blueprints
- **THEN** it SHALL return `{"ok": true, "blueprints": [{"name": "...", "path": "...", "parent_class": "..."}, ...]}`

### Requirement: Compile a Blueprint
The server SHALL expose a `compile_blueprint` tool that triggers a full compile of a Blueprint asset and reports any errors or warnings.

#### Scenario: Blueprint compiles cleanly
- **WHEN** `compile_blueprint` is called on a valid Blueprint path and compilation succeeds
- **THEN** it SHALL return `{"ok": true, "warnings": []}`

#### Scenario: Blueprint has compile errors
- **WHEN** `compile_blueprint` is called and the blueprint has errors
- **THEN** it SHALL return `{"ok": false, "errors": ["..."], "warnings": ["..."]}`

### Requirement: Add a variable to a Blueprint
The server SHALL expose an `add_variable` tool that adds a new variable to a Blueprint's property list with a specified name, type, and default value.

#### Scenario: Variable added
- **WHEN** `add_variable` is called with a valid blueprint path, variable name, type (e.g. `Float`, `Boolean`, `Vector`, `Object`), and optional default value
- **THEN** the variable SHALL be added and the tool SHALL return `{"ok": true}`

#### Scenario: Variable already exists
- **WHEN** `add_variable` is called with a name that already exists in the blueprint
- **THEN** it SHALL return `{"ok": false, "error": "Variable '<name>' already exists in blueprint"}`

### Requirement: Add a function to a Blueprint
The server SHALL expose an `add_function` tool that creates a new empty function graph in a Blueprint with a specified name.

#### Scenario: Function added
- **WHEN** `add_function` is called with a valid blueprint path and function name
- **THEN** an empty function graph SHALL be created and the tool SHALL return `{"ok": true}`

### Requirement: Get Blueprint information
The server SHALL expose a `get_blueprint_info` tool that returns the variables, functions, and component hierarchy of a Blueprint asset.

#### Scenario: Blueprint info returned
- **WHEN** `get_blueprint_info` is called with a valid blueprint path
- **THEN** it SHALL return `{"ok": true, "parent_class": "...", "variables": [...], "functions": [...], "components": [...]}`

### Requirement: Call a function on a Blueprint instance or CDO
The server SHALL expose a `call_function` tool that calls a named Blueprint function on either a named actor in the current level or the Blueprint class default object (CDO), and returns the result.

#### Scenario: Function called on level actor
- **WHEN** `call_function` is called with an actor label and function name
- **THEN** the function SHALL be invoked on that actor and the tool SHALL return `{"ok": true, "result": <return value>}`

#### Scenario: Function not found
- **WHEN** `call_function` is called with a function name that does not exist on the target
- **THEN** it SHALL return `{"ok": false, "error": "Function '<name>' not found on target"}`

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
