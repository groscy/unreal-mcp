## REMOVED Requirements

### Requirement: UE5 editor displays MCP connection status in toolbar
**Reason**: Replaced by the `mcp-ue5-status-plugin` capability, which provides the same toolbar status display via a C++ Slate widget driven by the heartbeat channel. The Python ToolMenus approach requires an active Remote Execution connection to update the label, making it unable to reflect the "Stopped" state when the server exits.
**Migration**: Install the `UnrealMCPStatus` C++ plugin from `ue5-plugin/UnrealMCPStatus/` in the repository. The C++ plugin automatically registers a toolbar widget with the same visual placement and richer state information.

### Requirement: Status label updates when MCP server connects
**Reason**: Replaced by the heartbeat channel `connected` event (see `mcp-heartbeat-channel` spec). The C++ plugin updates its Slate widget directly on receiving the event — no Python remote execution required.
**Migration**: No action needed. The C++ plugin handles this automatically once installed.

### Requirement: Status label updates when MCP server disconnects
**Reason**: Replaced by the heartbeat channel `stopped` event and socket-close detection. The C++ plugin transitions to "Stopped" state on socket close or explicit `stopped` event, which is more reliable than trying to execute Python over a closing RE connection.
**Migration**: No action needed. The C++ plugin handles this automatically once installed.

### Requirement: UE5-side status module is auto-loaded at editor startup
**Reason**: The `unreal_mcp_status.py` Python module and `init_unreal.py` provisioning are no longer required for status display. The C++ plugin auto-loads via UE5's standard plugin system.
**Migration**: After installing the C++ plugin, the `init_unreal.py` import line for `unreal_mcp_status` may be removed. The Python module file may be deleted from `Content/Python/`. The `provisioning.py` module in the Python server will be removed in a follow-up change.

### Requirement: MCP server provisions the UE5 status module on first connect
**Reason**: Server-side file provisioning is replaced by the repository-distributed C++ plugin that users install once. Provisioning via Remote Execution was fragile (depends on a working connection to write files that need to exist before the connection is healthy).
**Migration**: The provisioning call in `server.py` will be removed. Users who relied on automatic provisioning should install the C++ plugin following the instructions in the project README.

## ADDED Requirements

### Requirement: Python provisioning path remains as deprecated fallback
The `provisioning.py` module and `push_ue_status()` calls SHALL remain in the codebase and continue to function for projects that have not yet installed the C++ plugin. These code paths SHALL be annotated with deprecation warnings in source comments.

#### Scenario: Project without C++ plugin installed
- **WHEN** the MCP server connects to a UE5 project that does not have the `UnrealMCPStatus` plugin
- **THEN** `provision_ue_status_module()` SHALL still be called and SHALL still write `unreal_mcp_status.py` and patch `init_unreal.py` as before

#### Scenario: Project with C++ plugin installed
- **WHEN** both the C++ plugin and the Python provisioning path are active
- **THEN** both MAY coexist; the Python module MAY be present and registered in `init_unreal.py` without conflicting with the C++ plugin's toolbar widget
