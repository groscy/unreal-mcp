"""Editor control tools."""

from __future__ import annotations

import json
from typing import Any

from ..connection import UEConnection


def play_in_editor(conn: UEConnection) -> dict[str, Any]:
    # PIE start is deferred to the next editor tick, so is_in_play_in_editor()
    # won't read True until a subsequent call — that's expected.
    code = """
import unreal, json
les = unreal.get_editor_subsystem(unreal.LevelEditorSubsystem)
if les.is_in_play_in_editor():
    print(json.dumps({"ok": False, "error": "PIE session is already running"}))
else:
    les.editor_request_begin_play()
    print(json.dumps({"ok": True, "note": "PIE begins on the next editor tick"}))
"""
    return _run_and_parse(conn, code)


def stop_play(conn: UEConnection) -> dict[str, Any]:
    code = """
import unreal, json
les = unreal.get_editor_subsystem(unreal.LevelEditorSubsystem)
if not les.is_in_play_in_editor():
    print(json.dumps({"ok": False, "error": "No PIE session is currently running"}))
else:
    les.editor_request_end_play()
    print(json.dumps({"ok": True}))
"""
    return _run_and_parse(conn, code)


def open_level(conn: UEConnection, level_path: str) -> dict[str, Any]:
    code = f"""
import unreal, json
level_path = {json.dumps(level_path)}
if not unreal.EditorAssetLibrary.does_asset_exist(level_path):
    print(json.dumps({{"ok": False, "error": f"Level not found: '{{level_path}}'"}}))
else:
    unreal.EditorLevelLibrary.load_level(level_path)
    print(json.dumps({{"ok": True, "level_path": level_path}}))
"""
    return _run_and_parse(conn, code)


def save_level(conn: UEConnection) -> dict[str, Any]:
    code = """
import unreal, json
world = unreal.EditorLevelLibrary.get_editor_world()
pkg = world.get_outer()
if pkg is None or pkg.get_name() == 'None' or not pkg.get_name().startswith('/'):
    print(json.dumps({"ok": False, "error": "Level has no save path. Use save_as or save the level manually first."}))
else:
    unreal.EditorLevelLibrary.save_current_level()
    print(json.dumps({"ok": True}))
"""
    return _run_and_parse(conn, code)


def run_console_command(conn: UEConnection, command: str) -> dict[str, Any]:
    code = f"""
import unreal, json
command = {json.dumps(command)}
unreal.SystemLibrary.execute_console_command(unreal.EditorLevelLibrary.get_editor_world(), command)
print(json.dumps({{"ok": True, "output": ""}}))
"""
    return _run_and_parse(conn, code)


def get_world_settings(conn: UEConnection) -> dict[str, Any]:
    code = """
import unreal, json
world = unreal.EditorLevelLibrary.get_editor_world()
ws = world.get_world_settings()
settings = {}
for prop_name in ['game_mode_override', 'gravity_z', 'world_to_meters', 'navigation_system_config']:
    try:
        settings[prop_name] = ws.get_editor_property(prop_name)
    except Exception:
        pass
# Convert non-serialisable UE objects to strings
serialisable = {}
for k, v in settings.items():
    try:
        json.dumps(v)
        serialisable[k] = v
    except (TypeError, ValueError):
        serialisable[k] = str(v)
print(json.dumps({"ok": True, "settings": serialisable}))
"""
    return _run_and_parse(conn, code)


def set_world_settings(conn: UEConnection, settings: dict[str, Any]) -> dict[str, Any]:
    code = f"""
import unreal, json
settings = {json.dumps(settings)}
world = unreal.EditorLevelLibrary.get_editor_world()
ws = world.get_world_settings()
updated = []
errors = []
for prop_name, value in settings.items():
    try:
        ws.set_editor_property(prop_name, value)
        updated.append(prop_name)
    except Exception as e:
        errors.append(prop_name)
if errors:
    print(json.dumps({{"ok": False, "error": f"Unknown world setting property: '{{errors[0]}}'"}}))
else:
    print(json.dumps({{"ok": True, "updated": updated}}))
"""
    return _run_and_parse(conn, code)


def _run_and_parse(conn: UEConnection, code: str) -> dict[str, Any]:
    result = conn.execute(code)
    if not result["ok"]:
        return result
    return _extract_json(result)


def _extract_json(result: dict[str, Any]) -> dict[str, Any]:
    stdout = (result.get("stdout") or "").strip()
    if stdout:
        try:
            return json.loads(stdout)
        except json.JSONDecodeError:
            pass
    if result.get("result") and isinstance(result["result"], dict):
        return result["result"]
    return result
