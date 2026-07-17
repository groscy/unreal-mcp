## Why

When the MCP server is running and connected to the UE5 editor, there is no visual feedback inside the editor itself — users must check terminal output or infer connectivity from tool behavior. A persistent UI indicator in the editor makes the MCP connection state immediately visible, reducing confusion during development sessions.

## What Changes

- A new Unreal Engine editor widget (slate panel or toolbar button) added via the existing Python-side editor integration that displays the MCP server's connection status.
- The widget polls or reacts to the MCP connection state and updates its label/icon to reflect: connected, disconnected, or error states.
- The indicator is injected into the UE5 editor UI (e.g., main toolbar or status bar) when the plugin initializes, and removed on shutdown.

## Capabilities

### New Capabilities
- `editor-mcp-status-indicator`: An editor UI element (toolbar button or status bar widget) rendered inside UE5 that shows whether the MCP server is currently connected. Displays connection state (connected / disconnected / error) with a color-coded icon or label.

### Modified Capabilities
<!-- No existing spec-level requirement changes needed -->

## Impact

- **UE5 plugin/editor Python scripts**: New Python code that creates and manages an Unreal editor widget using `unreal.EditorUtilityWidget` or slate-level APIs; runs on the UE5 side and reads connection status from the MCP server (via a lightweight heartbeat or shared state).
- **MCP server**: May expose a status endpoint or broadcast connection events that the UE5 widget can poll.
- **No breaking changes** to existing MCP tools or the remote-connection protocol.
