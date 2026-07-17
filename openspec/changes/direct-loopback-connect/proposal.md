## Why

The single most common connection failure is "the editor is running with Remote Execution enabled, but the MCP server never connects." On the typical deployment — UE5 and the MCP server on the **same Windows machine** — the root cause is **UDP multicast discovery**, not the command channel:

- UE binds its discovery socket to `127.0.0.1` by default, but `connection.py` binds the Python side to `0.0.0.0`, so the OS picks the multicast interface by routing table — frequently a virtual adapter (Hyper-V / WSL2 / Docker / VPN) rather than loopback.
- Even when both sides agree on `127.0.0.1`, Windows handles **multicast over the loopback path** poorly, so the discovery `pong` is often never delivered.
- The result is a silent 15 s `"no nodes discovered"` timeout, and the exponential-backoff reconnect loop simply repeats the identical broken multicast setup forever.

Inspection of the UE 5.7 engine source (`PythonScriptRemoteExecution.cpp`) confirms two facts that make discovery **avoidable entirely on localhost**:

1. The receive filter accepts any message whose `dest` is empty: `Dest.IsEmpty() || Dest.Equals(InNodeId)` (line 124). So the editor's node id is not needed.
2. An `open_connection` message makes the editor **actively TCP-connect back** to the `command_ip`/`command_port` we supply (`HandleOpenConnectionMessage` → `OpenCommandConnection` → `Connect()`, lines 374–402, 465).

Therefore a `dest`-less `open_connection` sent as **unicast UDP** to `127.0.0.1:6766` triggers the editor to dial back over loopback TCP — with no multicast, no `pong`, no discovery, and no firewall surface (Windows never filters loopback). A live spike against the running editor confirmed the full chain end to end.

## What Changes

- **New direct-connect transport** in `remote_execution.py`: a discovery-free path that sends a `dest`-less `open_connection` (unicast UDP to the configured RE bind host), accepts the editor's TCP back-connection, and runs commands with `dest` omitted. This becomes the **default** connection strategy.
- **Multicast discovery retained as a fallback** for the cross-machine case, selectable via a connection-mode setting (`auto` / `direct` / `discovery`, default `auto`: try direct first, fall back to discovery).
- **Non-blocking startup**: `_run()` no longer blocks the asyncio event loop on the initial `connect()`; the existing background reconnect task owns the first connection attempt so the MCP server completes its initialization handshake instantly and reports `CONNECTING`.
- **Command-channel read timeout**: the TCP command socket gets a configurable receive timeout so a hung/busy editor surfaces as a structured error and triggers reconnect, instead of blocking the call forever.
- **Config alignment & docs**: default `UE_MULTICAST_BIND` matches UE's `127.0.0.1` default; new `UE_CONNECT_MODE` and `UE_COMMAND_RECV_TIMEOUT` env vars documented; README env table corrected (`UE_CONNECT_TIMEOUT` default is `15.0`, not `3.0`) and a Windows multicast/loopback troubleshooting note added.

## Capabilities

### Modified Capabilities

- `remote-connection`: Adds a discovery-free direct loopback transport as the default connection strategy, keeps multicast discovery as a fallback, makes startup connection non-blocking, and adds a command-channel read timeout. No change to any MCP tool or to the UE5 side.

## Impact

- Modified files: `src/unreal_mcp/remote_execution.py`, `src/unreal_mcp/connection.py`, `src/unreal_mcp/server.py`, `README.md`
- New tests: direct-connect handshake unit tests (mocked socket), connect-mode selection, recv-timeout behavior
- **No UE5-side changes**: works against the stock `PythonScriptPlugin` with default settings; the `UnrealMCPStatus` plugin is unaffected
- **No protocol or tool changes**: the wire format is unchanged; only how the command channel is established differs
- Backwards compatible: discovery still works via `UE_CONNECT_MODE=discovery`; environment-variable defaults change but remain overridable

## Non-Goals

- Length-prefixed message framing on the command channel — the stock UE side also relies on packet-boundary framing, so a robust fix needs UE cooperation; tracked separately.
- Hardening cross-machine multicast discovery (multi-interface join, real-NIC auto-detect) — out of scope for the localhost-focused fix.
- Any change to the `UnrealMCPStatus` heartbeat channel or status UI.
