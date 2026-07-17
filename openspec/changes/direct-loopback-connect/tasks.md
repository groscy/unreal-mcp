## 1. Direct-connect transport in `remote_execution.py`

- [x] 1.1 Add a method on `_RemoteExecutionBroadcastConnection` (or a new lightweight sender) to send a single `open_connection` message **unicast** to a given `(host, port)` with `dest` omitted and `source` = session node id — reusing `_RemoteExecutionMessage` / `to_json_bytes`
- [x] 1.2 Add `RemoteExecution.open_command_connection_direct(host, port)` that: opens the TCP command listen socket (reuse `_RemoteExecutionCommandConnection._init_command_listen_socket`), then loops sending the unicast `open_connection` and attempting `accept()` on a bounded retry budget, returning success once the back-connection lands
- [x] 1.3 Ensure `run_command` sends `command` messages with `dest` omitted when the connection was established via the direct path (the existing `_RemoteExecutionMessage` already omits empty dest — confirm `remote_node_id` is not required and command-channel filter passes)
- [x] 1.4 Do not join any multicast group or start the broadcast listen thread in the direct path (no `pong` is awaited)

## 2. `connection.py`: config, mode selection, wiring

- [x] 2.1 Add env-var config: `UE_CONNECT_MODE` (`auto`|`direct`|`discovery`, default `auto`), `UE_CONNECT_HOST` (default = `UE_MULTICAST_BIND` value), `UE_COMMAND_RECV_TIMEOUT` (generous default, e.g. 30 s)
- [x] 2.2 Change `UE_MULTICAST_BIND` default from `0.0.0.0` to `127.0.0.1` to match UE's RE default
- [x] 2.3 Add `connect_direct()` to `UEConnection` that drives `open_command_connection_direct` and sets state to `CONNECTED` on success (mirrors `connect()` cleanup/teardown and `push_ue_status` behavior)
- [x] 2.4 Refactor `connect()` into a mode dispatcher: `auto` → try `connect_direct`, fall back to discovery `connect`; `direct`/`discovery` → single path. Preserve existing state transitions and `_last_error` reporting
- [x] 2.5 Apply `settimeout(UE_COMMAND_RECV_TIMEOUT)` to the accepted command socket so `_receive_message` raises `socket.timeout` (an `OSError`) on a hung editor; verify `execute()`'s existing `except (ConnectionError, OSError, RuntimeError)` path flags `RECONNECTING`

## 3. `server.py`: non-blocking startup

- [x] 3.1 Remove the synchronous `conn.connect()` call from `_run()` before `stdio_server()`; set initial state to `CONNECTING` and let `run_reconnect_loop` perform the first attempt
- [x] 3.2 Move the `provision_ue_status_module(...)` call so it runs after a successful (re)connect rather than gating startup (or invoke it from the reconnect success path); confirm it no longer blocks startup
- [x] 3.3 Confirm shutdown ordering (heartbeat → reconnect → `conn.disconnect()`) is unchanged and still clean

## 4. Tests

- [x] 4.1 Unit test: direct transport sends a `dest`-less `open_connection` with correct `source`/`command_ip`/`command_port` (assert on serialized bytes via a mocked UDP socket)
- [x] 4.2 Unit test: `open_command_connection_direct` returns success when a mock peer connects to the listen socket, and fails cleanly when the retry budget is exhausted
- [x] 4.3 Unit test: mode dispatcher — `auto` falls back to discovery when direct fails; `direct`/`discovery` use only their path (patch `connect_direct` / `connect` discovery)
- [x] 4.4 Unit test: a `socket.timeout` from the command socket causes `execute()` to return the connection error and set state to `RECONNECTING`
- [x] 4.5 Run the full suite (`uv run pytest`) and confirm no regressions in the existing snippet-generation tests

## 5. Docs

- [x] 5.1 README: document `UE_CONNECT_MODE`, `UE_CONNECT_HOST`, `UE_COMMAND_RECV_TIMEOUT`; correct the `UE_CONNECT_TIMEOUT` default (`15.0`, not `3.0`) and the `UE_MULTICAST_BIND` default
- [x] 5.2 README troubleshooting: add a "never connects on Windows / multicast" note explaining the direct-connect default, and the fallback knob (`UE_CONNECT_MODE=discovery`, `UE_CONNECT_HOST=<NIC>`) for editors whose RE bind address is a real adapter or for cross-machine setups
- [x] 5.3 Note that the direct transport requires no UE5-side changes and works against the stock `PythonScriptPlugin` with default settings

## 6. Manual verification (live editor)

- [x] 6.1 With the editor open (RE enabled, default settings), start the MCP server and confirm it reaches `CONNECTED` via the direct path with no multicast (e.g. via logs / `ping`)
- [x] 6.2 Confirm a tool call (`list_actors` or `ping`) round-trips successfully
- [x] 6.3 Confirm `UE_CONNECT_MODE=discovery` still connects (fallback path intact)
