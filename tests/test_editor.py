"""Tests for editor control tool snippet generation — no live UE required."""

import json
from unittest.mock import MagicMock

from unreal_mcp.tools import editor


def _make_conn(stdout: str = "", ok: bool = True) -> MagicMock:
    conn = MagicMock()
    conn.execute.return_value = {"ok": ok, "stdout": stdout, "result": None, "error": None}
    return conn


class TestPlayInEditor:
    def test_pie_guard_in_code(self):
        conn = _make_conn(stdout=json.dumps({"ok": True}))
        editor.play_in_editor(conn)
        code = conn.execute.call_args[0][0]
        assert "is_play_in_editor" in code
        assert "play_level_in_viewport" in code

    def test_already_running_error_message_in_code(self):
        conn = _make_conn(stdout=json.dumps({"ok": False, "error": "PIE session is already running"}))
        editor.play_in_editor(conn)
        code = conn.execute.call_args[0][0]
        assert "already running" in code


class TestStopPlay:
    def test_stop_guard_in_code(self):
        conn = _make_conn(stdout=json.dumps({"ok": True}))
        editor.stop_play(conn)
        code = conn.execute.call_args[0][0]
        assert "is_play_in_editor" in code
        assert "end_play" in code

    def test_not_running_error_in_code(self):
        conn = _make_conn(stdout=json.dumps({"ok": True}))
        editor.stop_play(conn)
        code = conn.execute.call_args[0][0]
        assert "currently running" in code


class TestOpenLevel:
    def test_level_path_in_code(self):
        conn = _make_conn(stdout=json.dumps({"ok": True, "level_path": "/Game/Levels/Main"}))
        editor.open_level(conn, "/Game/Levels/Main")
        code = conn.execute.call_args[0][0]
        assert "/Game/Levels/Main" in code
        assert "load_level" in code
        assert "does_asset_exist" in code


class TestSaveLevel:
    def test_unsaved_path_guard_in_code(self):
        conn = _make_conn(stdout=json.dumps({"ok": True}))
        editor.save_level(conn)
        code = conn.execute.call_args[0][0]
        assert "save_current_level" in code
        assert "no save path" in code


class TestRunConsoleCommand:
    def test_command_in_code(self):
        conn = _make_conn(stdout=json.dumps({"ok": True, "output": ""}))
        editor.run_console_command(conn, "stat fps")
        code = conn.execute.call_args[0][0]
        assert "stat fps" in code
        assert "execute_console_command" in code


class TestGetWorldSettings:
    def test_world_settings_properties_in_code(self):
        conn = _make_conn(stdout=json.dumps({"ok": True, "settings": {}}))
        editor.get_world_settings(conn)
        code = conn.execute.call_args[0][0]
        assert "get_world_settings" in code
        assert "gravity_z" in code


class TestSetWorldSettings:
    def test_settings_dict_in_code(self):
        conn = _make_conn(stdout=json.dumps({"ok": True, "updated": ["gravity_z"]}))
        editor.set_world_settings(conn, {"gravity_z": -980.0})
        code = conn.execute.call_args[0][0]
        assert "gravity_z" in code
        assert "set_editor_property" in code

    def test_unknown_property_guard_in_code(self):
        conn = _make_conn(stdout=json.dumps({"ok": True, "updated": []}))
        editor.set_world_settings(conn, {"fake_prop": 1})
        code = conn.execute.call_args[0][0]
        assert "Unknown world setting property" in code
