"""Singleton UEConnection wrapping the Remote Execution protocol."""

from __future__ import annotations

import logging
import os
import time
from typing import Any

from .remote_execution import (
    DEFAULT_MULTICAST_GROUP_ENDPOINT,
    DEFAULT_MULTICAST_BIND_ADDRESS,
    DEFAULT_COMMAND_ENDPOINT,
    MODE_EXEC_FILE,
    RemoteExecution,
    RemoteExecutionConfig,
)

logger = logging.getLogger(__name__)

_CONNECT_TIMEOUT = float(os.environ.get("UE_CONNECT_TIMEOUT", "5.0"))
_MULTICAST_GROUP = os.environ.get("UE_MULTICAST_GROUP", DEFAULT_MULTICAST_GROUP_ENDPOINT[0])
_MULTICAST_PORT = int(os.environ.get("UE_MULTICAST_PORT", str(DEFAULT_MULTICAST_GROUP_ENDPOINT[1])))
_COMMAND_HOST = os.environ.get("UE_COMMAND_HOST", DEFAULT_COMMAND_ENDPOINT[0])
_COMMAND_PORT = int(os.environ.get("UE_COMMAND_PORT", str(DEFAULT_COMMAND_ENDPOINT[1])))

_ERROR_NOT_CONNECTED = (
    "UE5 editor not connected. Ensure the editor is running with Remote Execution enabled."
)


class UEConnection:
    """Manages a single persistent connection to a UE5 editor via Remote Execution."""

    def __init__(self) -> None:
        self._re: RemoteExecution | None = None
        self.is_connected = False
        self._last_error: str = ""

    # ------------------------------------------------------------------
    # Lifecycle
    # ------------------------------------------------------------------

    def connect(self) -> bool:
        """Attempt to discover and connect to a UE5 editor. Returns True on success."""
        config = RemoteExecutionConfig()
        config.multicast_group_endpoint = (_MULTICAST_GROUP, _MULTICAST_PORT)
        config.command_endpoint = (_COMMAND_HOST, _COMMAND_PORT)

        re = RemoteExecution(config)
        try:
            re.start()
            # Wait for a node to appear via UDP discovery
            deadline = time.monotonic() + _CONNECT_TIMEOUT
            node_id = None
            while time.monotonic() < deadline:
                nodes = re.remote_nodes
                if nodes:
                    node_id = nodes[0]["node_id"]
                    break
                time.sleep(0.1)

            if node_id is None:
                re.stop()
                self._last_error = "Timed out waiting for UE5 editor (no nodes discovered)"
                logger.warning(self._last_error)
                return False

            re.open_command_connection(node_id)
            self._re = re
            self.is_connected = True
            self._last_error = ""
            logger.info("Connected to UE5 editor (node: %s)", node_id)
            self.push_ue_status("connected")
            return True
        except Exception as exc:
            try:
                re.stop()
            except Exception:
                pass
            self._last_error = str(exc)
            logger.warning("Failed to connect to UE5: %s", exc)
            return False

    def disconnect(self) -> None:
        if self._re:
            try:
                self.push_ue_status("disconnected")
            except Exception as exc:
                logger.warning("unreal-mcp: exception during disconnect status push: %s", exc)
            try:
                self._re.stop()
            except Exception:
                pass
            self._re = None
        self.is_connected = False

    def push_ue_status(self, state: str) -> None:
        """Execute a status-push snippet in UE5; log a warning on failure (never raises)."""
        code = f"import unreal_mcp_status; unreal_mcp_status.set_status({state!r})"
        result = self.execute(code)
        if not result["ok"]:
            logger.warning(
                "unreal-mcp: failed to push UE status '%s': %s",
                state,
                result.get("error"),
            )

    def reconnect(self) -> bool:
        self.disconnect()
        return self.connect()

    # ------------------------------------------------------------------
    # Core execution
    # ------------------------------------------------------------------

    def execute(self, code: str) -> dict[str, Any]:
        """Send Python code to UE5 and return structured result.

        Returns {"ok": bool, "stdout": str, "result": any, "error": str | None}
        """
        if not self.is_connected or self._re is None:
            return {"ok": False, "stdout": "", "result": None, "error": _ERROR_NOT_CONNECTED}

        try:
            raw = self._re.run_command(code, unattended=True, exec_mode=MODE_EXEC_FILE)
            return _parse_result(raw)
        except (ConnectionError, OSError, RuntimeError) as exc:
            logger.warning("Connection lost, attempting reconnect: %s", exc)
            self.is_connected = False
            if self.reconnect():
                try:
                    raw = self._re.run_command(code, unattended=True, exec_mode=MODE_EXEC_FILE)  # type: ignore[union-attr]
                    return _parse_result(raw)
                except Exception as exc2:
                    self.is_connected = False
                    return {"ok": False, "stdout": "", "result": None, "error": str(exc2)}
            return {"ok": False, "stdout": "", "result": None, "error": _ERROR_NOT_CONNECTED}
        except Exception as exc:
            return {"ok": False, "stdout": "", "result": None, "error": str(exc)}

    # ------------------------------------------------------------------
    # Health check
    # ------------------------------------------------------------------

    def ping(self) -> dict[str, Any]:
        """Return connection status and UE version without executing user code."""
        if not self.is_connected:
            return {"ok": False, "connected": False, "error": self._last_error or _ERROR_NOT_CONNECTED}

        result = self.execute("import unreal; print(unreal.SystemLibrary.get_engine_version())")
        if result["ok"]:
            version = (result.get("stdout") or "").strip()
            return {"ok": True, "connected": True, "ue_version": version}
        return {"ok": False, "connected": False, "error": result.get("error", "Unknown error")}


def _parse_result(raw: dict[str, Any]) -> dict[str, Any]:
    """Normalise a raw Remote Execution result into our standard shape.

    UE5 command_result data has:
        success  : bool
        result   : str  (stdout + any printed output)
        output   : list of {type, output} (optional, depends on exec mode)
    """
    success: bool = raw.get("success", False)

    # UE5 result format:
    #   output: list of {type: 'Info'|'Warning'|'Error', output: str}
    #   result: str (repr of last expression, or 'None')
    output_list = raw.get("output") or []
    stdout_parts = [item.get("output", "") for item in output_list if item.get("type", "").lower() in ("info", "stdout", "log")]
    error_parts = [item.get("output", "") for item in output_list if item.get("type", "").lower() in ("error", "exception", "stderr", "critical")]
    stdout = "".join(stdout_parts).rstrip("\r\n")
    error: str | None = "".join(error_parts).rstrip("\r\n") if error_parts else None
    result_str = raw.get("result", "None") or "None"
    # When success=False the result field contains the traceback/error string
    if not success and not error and result_str and result_str != "None":
        error = result_str.rstrip("\r\n")
    result_value = _try_parse_json(result_str) if result_str and result_str != "None" and success else None
    ok = success and not error_parts

    return {
        "ok": ok,
        "stdout": stdout,
        "result": result_value,
        "error": error,
    }


def _try_parse_json(value: Any) -> Any:
    if isinstance(value, str) and value:
        import json
        try:
            return json.loads(value)
        except (json.JSONDecodeError, ValueError):
            return value
    return value


# Module-level singleton used by all tool modules
_connection: UEConnection | None = None


def get_connection() -> UEConnection:
    global _connection
    if _connection is None:
        _connection = UEConnection()
    return _connection
