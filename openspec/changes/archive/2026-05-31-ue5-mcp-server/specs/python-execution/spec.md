## ADDED Requirements

### Requirement: Execute arbitrary Python in UE5 context
The server SHALL expose an `execute_python` tool that sends an arbitrary Python code string to the UE5 editor via Remote Execution and returns the combined stdout output and any explicit return value.

#### Scenario: Code executes successfully
- **WHEN** `execute_python` is called with a valid Python code string
- **THEN** the code SHALL be executed inside the UE editor process with access to the full `unreal` module, and the tool SHALL return `{"ok": true, "stdout": "<captured output>", "result": <last expression value or null>}`

#### Scenario: Code raises an exception
- **WHEN** `execute_python` is called with code that raises a Python exception
- **THEN** the tool SHALL return `{"ok": false, "error": "<exception type>: <message>", "traceback": "<traceback string>"}`

#### Scenario: Code produces no output
- **WHEN** `execute_python` is called with code that runs silently
- **THEN** the tool SHALL return `{"ok": true, "stdout": "", "result": null}`

### Requirement: No sandboxing or restrictions on execute_python
The `execute_python` tool SHALL impose no restrictions on the code it accepts. It SHALL not filter, validate, or refuse any code string.

#### Scenario: Potentially destructive code is submitted
- **WHEN** `execute_python` is called with code that modifies or deletes editor state
- **THEN** the code SHALL be forwarded to UE5 without modification or warning

### Requirement: execute_python is the foundation for all other tools
All dedicated tool implementations (e.g. `place_actor`, `compile_blueprint`) SHALL be implemented by constructing a Python code string and calling through the same Remote Execution channel used by `execute_python`. There SHALL be no alternative code path per tool on the UE side.

#### Scenario: Dedicated tool executes internally
- **WHEN** any named tool other than `execute_python` is invoked
- **THEN** the server SHALL internally construct a Python snippet and send it through Remote Execution, functionally equivalent to calling `execute_python` with that snippet
