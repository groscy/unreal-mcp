"""Provisions the UE5-side MCP status module on server connect.

.. deprecated::
    This entire module (and the ``set_status``/``push_ue_status`` flow it relies
    on) is superseded by the ``UnrealMCPStatus`` C++ plugin under ``ue5-plugin/``,
    which drives the toolbar status widget over the dedicated heartbeat channel
    (see ``heartbeat.py``) instead of Remote Execution. It is kept as a fallback
    for projects that have not yet installed the C++ plugin and will be removed in
    a follow-up change once the plugin is adopted.
"""

from __future__ import annotations

import base64
import json
import logging
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from .connection import UEConnection

logger = logging.getLogger(__name__)

_IMPORT_LINE = "import unreal_mcp_status"

# Written to Content/Python/unreal_mcp_status.py.
# Always overwritten on connect so the on-disk copy stays current.
_STATUS_MODULE_CONTENT = """\
import datetime as _dt
import json as _json
import os as _os
import subprocess as _subprocess

_status = {"state": "disconnected", "updated_at": None}
_server_command = None
_starting = False
_menu_entry = None
_toolbar_ext = None

_CONFIG_PATH = _os.path.join(_os.path.dirname(_os.path.abspath(__file__)), "unreal_mcp_config.json")


def _load_config():
    global _server_command
    try:
        if _os.path.exists(_CONFIG_PATH):
            with open(_CONFIG_PATH, encoding="utf-8") as f:
                cfg = _json.load(f)
            _server_command = cfg.get("server_command")
    except Exception:
        pass


def set_status(state):
    global _starting
    _starting = False
    _status["state"] = state
    _status["updated_at"] = _dt.datetime.now().isoformat()
    _rebuild_toolbar()


def set_server_command(command):
    global _server_command
    _server_command = command
    _rebuild_toolbar()


def start_server():
    global _starting
    if _status.get("state") == "connected" or _starting:
        return
    if not _server_command:
        try:
            import unreal as _ue
            _ue.log_warning("unreal_mcp_status: no server command configured")
        except Exception:
            pass
        return
    _starting = True
    try:
        import platform
        kwargs = {}
        if platform.system() == "Windows":
            kwargs["creationflags"] = _subprocess.CREATE_NEW_CONSOLE
        _subprocess.Popen(_server_command, shell=False, **kwargs)
    except Exception as exc:
        _starting = False
        try:
            import unreal as _ue
            _ue.log_warning("unreal_mcp_status: failed to start server: " + str(exc))
        except Exception:
            pass


def _get_label():
    if _status.get("state") == "connected":
        return "MCP: Connected"
    return "MCP: Disconnected"


def _get_tooltip():
    if _status.get("state") == "connected":
        return "MCP server is connected"
    elif _server_command:
        return "Click to start MCP server"
    else:
        return "MCP server not configured (connect once to enable)"


def _rebuild_toolbar():
    global _menu_entry, _toolbar_ext
    try:
        import unreal
        menus = unreal.ToolMenus.get()
        if _menu_entry is None:
            _toolbar_ext = menus.extend_menu("LevelEditor.LevelEditorToolBar.PlayToolBar")
            _menu_entry = unreal.ToolMenuEntry(
                name="MCPStatusLabel",
                type=unreal.MultiBlockType.TOOL_BAR_BUTTON,
            )
            _menu_entry.set_label(_get_label())
            _menu_entry.set_tool_tip(_get_tooltip())
            _menu_entry.set_string_command(
                unreal.ToolMenuStringCommandType.PYTHON,
                "",
                "import unreal_mcp_status; unreal_mcp_status.start_server()",
            )
            _toolbar_ext.add_menu_entry("", _menu_entry)
        else:
            _menu_entry.set_label(_get_label())
            _menu_entry.set_tool_tip(_get_tooltip())
        menus.refresh_all_widgets()
    except Exception as exc:
        try:
            import unreal as _ue
            _ue.log_warning("unreal_mcp_status: toolbar update skipped: " + str(exc))
        except Exception:
            pass


_load_config()
_rebuild_toolbar()
"""


def provision_ue_status_module(conn: "UEConnection", server_command: list[str] | None = None) -> None:
    """Orchestrate project-path resolution, file writing, and init_unreal.py patching."""
    project_dir = _resolve_project_dir(conn)
    if not project_dir:
        logger.warning(
            "unreal-mcp: could not determine UE5 project path; "
            "skipping status module provisioning"
        )
        return

    content_python = project_dir.rstrip("/\\") + "/Content/Python"
    _write_status_module(conn, content_python)
    _patch_init_unreal(conn, content_python)
    if server_command:
        _write_config(conn, content_python, server_command)
        _push_server_command(conn, server_command)


def _resolve_project_dir(conn: "UEConnection") -> str:
    result = conn.execute("import unreal; print(unreal.Paths.project_dir())")
    if not result["ok"]:
        return ""
    return (result.get("stdout") or "").strip()


def _write_status_module(conn: "UEConnection", content_python: str) -> None:
    """Always overwrite unreal_mcp_status.py so the on-disk copy stays current."""
    status_path = content_python + "/unreal_mcp_status.py"
    encoded = base64.b64encode(_STATUS_MODULE_CONTENT.encode()).decode()

    code = (
        "import os, base64\n"
        f"path = {status_path!r}\n"
        "os.makedirs(os.path.dirname(path), exist_ok=True)\n"
        f"with open(path, 'wb') as f:\n"
        f"    f.write(base64.b64decode({encoded!r}))\n"
        "print('written')\n"
    )
    result = conn.execute(code)
    if (result.get("stdout") or "").strip() == "written":
        logger.info("unreal-mcp: wrote unreal_mcp_status.py to %s", status_path)
    else:
        logger.warning("unreal-mcp: unexpected result writing status module: %s", result)

    # Reload the live module so the new code is active without a UE5 restart.
    # Preserve _status and _server_command across the reload so the toolbar
    # label and server command are not reset to their module-level defaults.
    conn.execute(
        "import sys, importlib\n"
        "mod = sys.modules.get('unreal_mcp_status')\n"
        "if mod:\n"
        "    _saved_status = dict(mod._status)\n"
        "    _saved_cmd = mod._server_command\n"
        "    importlib.reload(mod)\n"
        "    mod._status.update(_saved_status)\n"
        "    if _saved_cmd is not None:\n"
        "        mod._server_command = _saved_cmd\n"
    )


def _write_config(conn: "UEConnection", content_python: str, server_command: list[str]) -> None:
    """Write unreal_mcp_config.json with the server launch command."""
    config_path = content_python + "/unreal_mcp_config.json"
    config_json = json.dumps({"server_command": server_command})
    encoded = base64.b64encode(config_json.encode()).decode()

    code = (
        "import os, base64\n"
        f"path = {config_path!r}\n"
        "os.makedirs(os.path.dirname(path), exist_ok=True)\n"
        f"with open(path, 'wb') as f:\n"
        f"    f.write(base64.b64decode({encoded!r}))\n"
        "print('written')\n"
    )
    result = conn.execute(code)
    if (result.get("stdout") or "").strip() == "written":
        logger.info("unreal-mcp: wrote unreal_mcp_config.json")
    else:
        logger.warning("unreal-mcp: unexpected result writing config: %s", result)


def _push_server_command(conn: "UEConnection", server_command: list[str]) -> None:
    """Push the server command into the live UE5 module (no restart needed)."""
    cmd_repr = repr(server_command)
    code = f"import unreal_mcp_status; unreal_mcp_status.set_server_command({cmd_repr})"
    result = conn.execute(code)
    if not result["ok"]:
        logger.warning("unreal-mcp: failed to push server command: %s", result.get("error"))


def _patch_init_unreal(conn: "UEConnection", content_python: str) -> None:
    """Append import line to init_unreal.py; create the file if absent."""
    init_path = content_python + "/init_unreal.py"

    code = (
        "import os\n"
        f"path = {init_path!r}\n"
        f"line = {_IMPORT_LINE!r}\n"
        "content = open(path, encoding='utf-8').read() if os.path.exists(path) else ''\n"
        "if line not in content.splitlines():\n"
        "    os.makedirs(os.path.dirname(path), exist_ok=True)\n"
        "    with open(path, 'a', encoding='utf-8') as f:\n"
        "        f.write('\\n' + line + '\\n')\n"
        "    print('appended')\n"
        "else:\n"
        "    print('present')\n"
    )
    result = conn.execute(code)
    stdout = (result.get("stdout") or "").strip()
    if stdout == "appended":
        logger.info("unreal-mcp: appended '%s' to %s", _IMPORT_LINE, init_path)
    elif stdout == "present":
        logger.info("unreal-mcp: import line already present in %s", init_path)
    else:
        logger.warning("unreal-mcp: unexpected result patching init_unreal.py: %s", result)
