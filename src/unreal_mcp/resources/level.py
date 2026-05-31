"""unreal://level/hierarchy resource — live actor tree."""

from __future__ import annotations

import json
from typing import Any

from ..connection import UEConnection

_CODE = """
import unreal, json
actors = []
try:
    for a in unreal.EditorLevelLibrary.get_all_level_actors():
        t = a.get_actor_transform()
        loc = t.translation
        rot = t.rotation.euler()
        sc = t.scale3d
        parent = a.get_attach_parent_actor()
        actors.append({
            "label": a.get_actor_label(),
            "class": a.get_class().get_name(),
            "parent": parent.get_actor_label() if parent else None,
            "location": [loc.x, loc.y, loc.z],
            "rotation": [rot.x, rot.y, rot.z],
            "scale": [sc.x, sc.y, sc.z],
        })
except Exception:
    pass
print(json.dumps({"actors": actors}))
"""


def get_hierarchy(conn: UEConnection) -> dict[str, Any]:
    result = conn.execute(_CODE)
    if not result["ok"]:
        return {"actors": []}
    stdout = (result.get("stdout") or "").strip()
    if stdout:
        try:
            return json.loads(stdout)
        except json.JSONDecodeError:
            pass
    return {"actors": []}
