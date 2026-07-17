## Context

The MCP server reaches UE5 through the Remote Execution (RE) protocol: a UDP multicast discovery phase (`ping`/`pong`) followed by a TCP command channel that the **editor opens back to the server** after receiving an `open_connection` message. `connection.py` orchestrates this via the vendored `remote_execution.py` (a near-verbatim copy of Epic's reference client).

On localhost Windows — the typical deployment — discovery is the weak link. Two independent problems:

1. **Interface mismatch.** `connection.py:36` defaults `UE_MULTICAST_BIND` to `0.0.0.0`, while UE defaults its `RemoteExecutionMulticastBindAddress` to `127.0.0.1`. With `0.0.0.0`, `IP_ADD_MEMBERSHIP` / `IP_MULTICAST_IF` (`remote_execution.py:266-267`) join the group on the OS default-route interface, which on a dev box is often a Hyper-V/WSL/Docker virtual adapter, not loopback.
2. **Loopback multicast on Windows is unreliable.** Even with both sides on `127.0.0.1`, the `pong` frequently never arrives.

Failure is silent: `connect()` waits `UE_CONNECT_TIMEOUT` (15 s) for a node, finds none, and the reconnect loop repeats the same broken setup indefinitely.

### Engine-source findings (UE 5.7 `PythonScriptRemoteExecution.cpp`)

A direct read of the editor side resolved whether discovery can be bypassed:

- **`pong` is always multicast.** `BroadcastPongMessage` → `BroadcastMessage` sends to `BroadcastGroupAddr` (`239.0.0.1:6766`), never unicast to the ping source (lines 422-433, 293). → *Unicast ping does not help; the response still rides the broken multicast path.* (This is why "Approach 3" was rejected.)
- **Empty `dest` passes the filter.** `PassesReceiveFilter`: `!Source.Equals(NodeId) && (Dest.IsEmpty() || Dest.Equals(NodeId))` (line 124). → *We never need the editor's node id.*
- **`open_connection` makes the editor dial back.** `HandleOpenConnectionMessage` reads `command_ip`/`command_port` and calls `OpenCommandConnection`, which does `CommandChannelSocket->Connect(...)` to our endpoint (lines 374-402, 465). → *The editor initiates the TCP connection to us.*
- **The discovery socket receives unicast.** It is bound to `MulticastBindAddress:6766` as reusable (lines 295-298); a unicast datagram to that address/port is delivered regardless of multicast. Loopback unicast is reliable on Windows.
- **Command round-trip needs no node id.** A `command` with empty `dest` passes the command-channel filter (line 525); the editor's `command_result` is addressed back with `dest = InMessage.Source` = our id (line 620), which passes our filter.

A throwaway spike (raw sockets, no project deps) ran the full chain against the live editor and reached a successful `command_result` — confirming the design empirically, not just from source reading.

## Goals / Non-Goals

**Goals:**
- Connect reliably on localhost without depending on multicast discovery at all.
- Keep working against the **stock** UE `PythonScriptPlugin` with default settings — zero UE-side changes.
- Preserve multicast discovery as an explicit fallback for cross-machine setups.
- Make startup non-blocking and make a hung command channel surface as an error rather than a freeze.

**Non-Goals:**
- Replacing or extending the RE wire protocol.
- Length-prefixed framing on the command channel (needs UE cooperation; the editor side also relies on packet boundaries).
- Cross-machine multicast hardening (multi-interface join, NIC auto-detect).
- Any change to MCP tools, resources, or the heartbeat/status plugin.

## Decisions

### Decision 1: Direct loopback connect via a `dest`-less `open_connection` (default transport)

**Chosen:** Add a `connect_direct(host)` path that:
1. Opens the TCP command **listen** socket on `command_endpoint` (default `127.0.0.1:6776`) — unchanged from today.
2. Sends a `dest`-less `open_connection` (`source` = our stable node id, `data` = our `command_ip`/`command_port`) as **unicast UDP** to `(host, multicast_port)` where `host` defaults to the configured RE bind address (`127.0.0.1`).
3. Re-sends every ~1 s, up to a bounded number of attempts, until `accept()` returns the editor's back-connection (mirrors the stock `_try_accept` retry of 6×).
4. Runs all subsequent `command` messages with `dest` omitted.

No multicast group is joined; no `pong` is awaited; the editor's node id is never learned or needed.

**Alternatives considered:**
- *Unicast ping → expect unicast pong (Approach 3):* rejected — the editor always multicasts its `pong` (source evidence above), so the response is still lost on broken-loopback Windows.
- *Fix multicast interface selection (join on all adapters / match bind):* helps but still relies on loopback multicast working, which is the unreliable part on Windows; keeps a whole fragile subsystem on the critical path.
- *Small UE-side C++ addition (direct unicast responder):* unnecessary — the stock editor already dials back from a `dest`-less `open_connection`; avoid touching the editor.

**Rationale:** Removes the entire broken subsystem (multicast, discovery, node-id exchange) from the localhost critical path while speaking the unmodified protocol. Pure-loopback also sidesteps Windows Firewall (loopback is never filtered).

### Decision 2: Connection-mode selection — `auto` (default) / `direct` / `discovery`

**Chosen:** `UE_CONNECT_MODE` env var. `auto` attempts `connect_direct` first and falls back to the existing discovery `connect()` if the back-connection never arrives. `direct` and `discovery` force one path (useful for debugging and cross-machine).

**Rationale:** Keeps a safety net for setups where the editor's RE bind address is a real NIC or the two processes are on different hosts, without making the common case pay for it. `auto` means existing users get the fix transparently.

**Edge case:** If the editor's `RemoteExecutionMulticastBindAddress` is a real NIC (not `127.0.0.1`/`0.0.0.0`), unicast to `127.0.0.1:6766` misses the socket. `auto` then falls back to discovery; `direct` users can point `UE_CONNECT_HOST` at that NIC. The spike's failure hint already documents this for users.

### Decision 3: Stable source node id; idempotent re-sends

**Chosen:** Reuse the existing per-session `RemoteExecution._node_id` (a UUID created once) as the `open_connection` source, and keep it stable across re-send attempts.

**Rationale:** The editor keys its command connection on `(RemoteNodeId, CommandEndpoint)` and skips re-creation when both match (`OpenCommandConnection`, line 700). A stable source makes repeated `open_connection` sends idempotent instead of tearing down and rebuilding the channel.

### Decision 4: Non-blocking startup

**Chosen:** Remove the synchronous `conn.connect()` from `_run()` before `stdio_server()` starts. Set state to `CONNECTING`/`DISCONNECTED` and let `run_reconnect_loop` perform the first connection (it already runs `connect` via `asyncio.to_thread`). The reconnect loop calls whichever transport `UE_CONNECT_MODE` selects.

**Rationale:** Today startup can block the event loop for up to 15 s of discovery (and previously up to 30 s of accept), risking an MCP initialization timeout. The background task already exists; routing the first attempt through it makes the server come up instantly.

### Decision 5: Command-channel read timeout

**Chosen:** Set a configurable `settimeout(UE_COMMAND_RECV_TIMEOUT)` (default e.g. 30 s) on the accepted command socket. A timeout raises `socket.timeout`, which `UEConnection.execute()` maps to a connection error and a transition to `RECONNECTING`.

**Rationale:** Today the command socket is pure-blocking with no timeout (`remote_execution.py:497`), so a busy editor (shader compile, modal dialog, long script) freezes the call indefinitely. `execute()` already catches `OSError` (a `socket.timeout` is an `OSError` subclass) and flags reconnect — so a timeout slots cleanly into the existing recovery path. The timeout must be generous enough not to abort legitimately long operations.

## Risks / Trade-offs

- **Editor RE bind is a real NIC:** direct-to-loopback misses it. Mitigated by `auto` fallback to discovery and `UE_CONNECT_HOST` override.
- **Recv timeout too short:** could abort a legitimately slow command. Mitigated by a generous default and env override; document the knob.
- **Large-result framing:** unchanged by this proposal and still relies on packet boundaries (a pre-existing risk on both sides). Explicitly a non-goal here; noted for follow-up.

## Migration

- Default behavior changes from discovery-first to direct-first (`auto`). Existing localhost users get the fix with no config change; anyone who specifically depends on discovery can set `UE_CONNECT_MODE=discovery`.
- `UE_MULTICAST_BIND` default changes `0.0.0.0` → `127.0.0.1` to match UE; override remains available for multi-adapter discovery use.
- New env vars: `UE_CONNECT_MODE`, `UE_CONNECT_HOST` (defaults to the multicast bind host), `UE_COMMAND_RECV_TIMEOUT`.
