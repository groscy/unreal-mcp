"""Actor management tools — thin Python-snippet generators."""

from __future__ import annotations

import json
from typing import Any

from ..connection import UEConnection
from ._util import pyval


def list_actors(conn: UEConnection) -> dict[str, Any]:
    code = """
import unreal, json
actors = []
for a in unreal.EditorLevelLibrary.get_all_level_actors():
    t = a.get_actor_transform()
    loc = t.translation
    rot = t.rotation.euler()
    sc = t.scale3d
    actors.append({
        "label": a.get_actor_label(),
        "class": a.get_class().get_name(),
        "location": [loc.x, loc.y, loc.z],
        "rotation": [rot.x, rot.y, rot.z],
        "scale": [sc.x, sc.y, sc.z],
    })
print(json.dumps({"ok": True, "actors": actors}))
"""
    return _run_and_parse(conn, code)


def get_actor_properties(conn: UEConnection, label: str) -> dict[str, Any]:
    code = f"""
import unreal, json
label = {json.dumps(label)}
actor = None
for a in unreal.EditorLevelLibrary.get_all_level_actors():
    if a.get_actor_label() == label:
        actor = a
        break
if actor is None:
    print(json.dumps({{"ok": False, "error": f"Actor '{{label}}' not found in the current level"}}))
else:
    props = {{}}
    for name in dir(actor):
        if name.startswith("_"):
            continue
        try:
            v = actor.get_editor_property(name)
            try:
                json.dumps(v)
                props[name] = v
            except (TypeError, ValueError):
                props[name] = str(v)
        except Exception:
            pass
    print(json.dumps({{"ok": True, "properties": props}}))
"""
    return _run_and_parse(conn, code)


def place_actor(
    conn: UEConnection,
    class_path: str,
    location: list[float] | None = None,
    rotation: list[float] | None = None,
    scale: list[float] | None = None,
) -> dict[str, Any]:
    loc = location or [0.0, 0.0, 0.0]
    rot = rotation or [0.0, 0.0, 0.0]
    sc = scale or [1.0, 1.0, 1.0]
    code = f"""
import unreal, json
class_path = {json.dumps(class_path)}
# Try as a C++ class first (e.g. /Script/Engine.PointLight), then as a Blueprint asset
if '/Script/' in class_path:
    cls = unreal.load_class(None, class_path)
elif '/' in class_path:
    bp = unreal.EditorAssetLibrary.load_asset(class_path)
    cls = bp.generated_class() if bp and hasattr(bp, 'generated_class') else None
else:
    cls = unreal.load_class(None, '/Script/Engine.' + class_path)
if cls is None:
    print(json.dumps({{"ok": False, "error": f"Class '{{class_path}}' not found"}}))
else:
    loc = unreal.Vector({loc[0]}, {loc[1]}, {loc[2]})
    rot = unreal.Rotator({rot[0]}, {rot[1]}, {rot[2]})
    actor = unreal.EditorLevelLibrary.spawn_actor_from_class(cls, loc, rot)
    if actor is None:
        print(json.dumps({{"ok": False, "error": "Failed to spawn actor"}}))
    else:
        actor.set_actor_scale3d(unreal.Vector({sc[0]}, {sc[1]}, {sc[2]}))
        print(json.dumps({{"ok": True, "label": actor.get_actor_label(), "name": actor.get_name()}}))
"""
    return _run_and_parse(conn, code)


def delete_actor(conn: UEConnection, label: str) -> dict[str, Any]:
    code = f"""
import unreal, json
label = {json.dumps(label)}
actor = None
for a in unreal.EditorLevelLibrary.get_all_level_actors():
    if a.get_actor_label() == label:
        actor = a
        break
if actor is None:
    print(json.dumps({{"ok": False, "error": f"Actor '{{label}}' not found"}}))
else:
    unreal.EditorLevelLibrary.destroy_actor(actor)
    print(json.dumps({{"ok": True}}))
"""
    return _run_and_parse(conn, code)


def set_actor_transform(
    conn: UEConnection,
    label: str,
    location: list[float] | None = None,
    rotation: list[float] | None = None,
    scale: list[float] | None = None,
) -> dict[str, Any]:
    code = f"""
import unreal, json
label = {json.dumps(label)}
actor = None
for a in unreal.EditorLevelLibrary.get_all_level_actors():
    if a.get_actor_label() == label:
        actor = a
        break
if actor is None:
    print(json.dumps({{"ok": False, "error": f"Actor '{{label}}' not found"}}))
else:
    location = {pyval(location)}
    rotation = {pyval(rotation)}
    scale = {pyval(scale)}
    if location is not None:
        actor.set_actor_location(unreal.Vector(*location), False, False)
    if rotation is not None:
        actor.set_actor_rotation(unreal.Rotator(*rotation), False)
    if scale is not None:
        actor.set_actor_scale3d(unreal.Vector(*scale))
    print(json.dumps({{"ok": True}}))
"""
    return _run_and_parse(conn, code)


def set_actor_property(
    conn: UEConnection,
    label: str,
    property_path: str,
    value: Any,
) -> dict[str, Any]:
    code = f"""
import unreal, json
label = {json.dumps(label)}
property_path = {json.dumps(property_path)}
value = {json.dumps(value)}
actor = None
for a in unreal.EditorLevelLibrary.get_all_level_actors():
    if a.get_actor_label() == label:
        actor = a
        break
if actor is None:
    print(json.dumps({{"ok": False, "error": f"Actor '{{label}}' not found"}}))
else:
    parts = property_path.split('.')
    target = actor
    for part in parts[:-1]:
        target = target.get_editor_property(part)
    prop_name = parts[-1]
    try:
        target.set_editor_property(prop_name, value)
        print(json.dumps({{"ok": True}}))
    except Exception as first_err:
        # If the value is a content path string, try loading it as an asset object first.
        # This handles asset-reference properties like StaticMesh, DecalMaterial, etc.
        loaded = False
        if isinstance(value, str) and '/' in value:
            try:
                asset_obj = unreal.EditorAssetLibrary.load_asset(value)
                if asset_obj is None:
                    asset_obj = unreal.load_object(None, value)
                if asset_obj is not None:
                    target.set_editor_property(prop_name, asset_obj)
                    loaded = True
            except Exception:
                pass
        if loaded:
            print(json.dumps({{"ok": True, "note": "value loaded as asset reference"}}))
        else:
            print(json.dumps({{"ok": False, "error": f"Property '{{property_path}}' on '{{label}}': {{first_err}}"}}))
"""
    return _run_and_parse(conn, code)


def inspect_pie_state(conn: UEConnection) -> dict[str, Any]:
    """Read key Battleforge gameplay state during a PIE session.

    Returns PowerPool, WellsHeld, MaxTier, hand/deck counts, base HP for both
    players, and mine ownership — enough to verify every smoke-test scenario.
    """
    code = """
import unreal, json

def safe(fn):
    try:
        return fn()
    except Exception as e:
        return f"err:{e}"

def get_pc(idx):
    try:
        return unreal.GameplayStatics.get_player_controller(None, idx)
    except Exception:
        return None

state = {"ok": True, "players": [], "mines": [], "bases": [], "wells": []}

for idx in range(2):
    pc = get_pc(idx)
    p = {"index": idx}
    if pc is None:
        p["error"] = "no PlayerController"
    else:
        p["power"]      = safe(lambda: pc.get_editor_property("power_pool"))
        p["wells_held"] = safe(lambda: pc.get_editor_property("wells_held"))
        p["class"]      = pc.get_class().get_name()
        # Hand/deck counts via HandManager component (if present)
        hm = safe(lambda: pc.get_editor_property("hand_manager"))
        if hm and not isinstance(hm, str):
            p["hand_count"] = safe(lambda: len(hm.get_editor_property("hand_cards")))
            p["deck_count"] = safe(lambda: len(hm.get_editor_property("deck_cards")))
    state["players"].append(p)

# Base HP
for a in unreal.EditorLevelLibrary.get_all_level_actors():
    cls = a.get_class().get_name()
    lbl = a.get_actor_label()
    if "PlayerBase" in cls or "BP_PlayerBase" in cls:
        state["bases"].append({
            "label": lbl,
            "owner": safe(lambda: a.get_editor_property("owner_player_index")),
            "hp":    safe(lambda: a.get_editor_property("hp")),
            "max_hp": safe(lambda: a.get_editor_property("max_hp")),
        })
    elif "Mine" in cls or "BP_Mine" in cls:
        state["mines"].append({
            "label": lbl,
            "owner": safe(lambda: a.get_editor_property("owner_player_index")),
            "progress": safe(lambda: a.get_editor_property("capture_progress")),
        })
    elif "ManaWell" in cls or "BP_ManaWell" in cls:
        state["wells"].append({
            "label": lbl,
            "owner": safe(lambda: a.get_editor_property("owner_player_index")),
        })

print(json.dumps(state, default=str))
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
