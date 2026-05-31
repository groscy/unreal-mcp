"""unreal://world/settings resource — live World Settings."""

from __future__ import annotations

import json
from typing import Any

from ..connection import UEConnection

_SETTINGS_PROPS = [
    "game_mode_override",
    "gravity_z",
    "world_to_meters",
    "ai_system",
    "navigation_system_config",
    "physics_collision_handler_class",
    "default_game_mode",
    "kill_z",
    "enable_world_bounds_checks",
]

_CODE = f"""
import unreal, json
world = unreal.EditorLevelLibrary.get_editor_world()
ws = world.get_world_settings()
props = {json.dumps(_SETTINGS_PROPS)}
settings = {{}}
for prop in props:
    try:
        v = ws.get_editor_property(prop)
        try:
            json.dumps(v)
            settings[prop] = v
        except (TypeError, ValueError):
            settings[prop] = str(v)
    except Exception:
        pass
print(json.dumps(settings))
"""


def get_settings(conn: UEConnection) -> dict[str, Any]:
    result = conn.execute(_CODE)
    if not result["ok"]:
        return {}
    stdout = (result.get("stdout") or "").strip()
    if stdout:
        try:
            return json.loads(stdout)
        except json.JSONDecodeError:
            pass
    return {}
