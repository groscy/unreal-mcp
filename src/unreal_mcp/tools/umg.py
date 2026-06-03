"""UMG / Widget Blueprint tools — UE 5.7 compatible."""

from __future__ import annotations

import json
from typing import Any

from ..connection import UEConnection


def _run_and_parse(conn: UEConnection, code: str) -> dict[str, Any]:
    result = conn.execute(code)
    if not result["ok"]:
        return result
    stdout = (result.get("stdout") or "").strip()
    if stdout:
        try:
            return json.loads(stdout)
        except json.JSONDecodeError:
            pass
    return result


def create_widget_blueprint(
    conn: UEConnection,
    asset_path: str,
    parent_class: str = "UserWidget",
) -> dict[str, Any]:
    """Create a Widget Blueprint asset."""
    code = f"""
import unreal, json
asset_path   = {json.dumps(asset_path)}
parent_name  = {json.dumps(parent_class)}
EAL = unreal.EditorAssetLibrary
BEL = unreal.BlueprintEditorLibrary

if EAL.does_asset_exist(asset_path):
    print(json.dumps({{"ok": False, "error": f"Already exists: {{asset_path}}"}}))
else:
    cls = (unreal.load_class(None, f'/Script/UMG.{{parent_name}}')
           or unreal.load_class(None, parent_name))
    if cls is None:
        print(json.dumps({{"ok": False, "error": f"Class not found: {{parent_name}}"}}))
    else:
        bp = BEL.create_blueprint_asset_with_parent(asset_path, cls)
        if bp:
            EAL.save_asset(asset_path)
            print(json.dumps({{"ok": True, "asset_path": asset_path}}))
        else:
            print(json.dumps({{"ok": False, "error": "Widget Blueprint creation failed"}}))
"""
    return _run_and_parse(conn, code)


def add_widget_variable(
    conn: UEConnection,
    asset_path: str,
    name: str,
    var_type: str,
) -> dict[str, Any]:
    """Add a variable to a Widget Blueprint (delegates to BEL.add_member_variable)."""
    code = f"""
import unreal, json
asset_path = {json.dumps(asset_path)}
var_name   = {json.dumps(name)}
var_type   = {json.dumps(var_type)}
EAL = unreal.EditorAssetLibrary
BEL = unreal.BlueprintEditorLibrary

_BASIC = {{
    "float":"real","real":"real","int":"int","bool":"bool",
    "string":"string","name":"name","text":"text","name[]":"name",
}}

def _pin(ts):
    ts = ts.strip()
    if ts.lower().startswith("array:"):
        return BEL.get_array_type(_pin(ts[6:]))
    lower = ts.lower()
    mapped = _BASIC.get(lower, lower)
    return BEL.get_basic_type_by_name(mapped)

bp = EAL.load_asset(asset_path)
if bp is None:
    print(json.dumps({{"ok": False, "error": f"Not found: {{asset_path}}"}}))
else:
    try:
        ok = BEL.add_member_variable(bp, var_name, _pin(var_type))
        if not ok:
            print(json.dumps({{"ok": False, "error": f"'{{var_name}}' already exists or failed"}}))
        else:
            BEL.compile_blueprint(bp)
            EAL.save_asset(asset_path)
            print(json.dumps({{"ok": True}}))
    except Exception as e:
        print(json.dumps({{"ok": False, "error": str(e)}}))
"""
    return _run_and_parse(conn, code)


def add_widget_function(
    conn: UEConnection,
    asset_path: str,
    name: str,
) -> dict[str, Any]:
    """Add a function stub to a Widget Blueprint."""
    code = f"""
import unreal, json
asset_path = {json.dumps(asset_path)}
func_name  = {json.dumps(name)}
EAL = unreal.EditorAssetLibrary
BEL = unreal.BlueprintEditorLibrary

bp = EAL.load_asset(asset_path)
if bp is None:
    print(json.dumps({{"ok": False, "error": f"Not found: {{asset_path}}"}}))
else:
    try:
        g = BEL.add_function_graph(bp, func_name)
        if g is None:
            print(json.dumps({{"ok": False, "error": f"'{{func_name}}' already exists or failed"}}))
        else:
            EAL.save_asset(asset_path)
            print(json.dumps({{"ok": True}}))
    except Exception as e:
        print(json.dumps({{"ok": False, "error": str(e)}}))
"""
    return _run_and_parse(conn, code)


def create_widget_layout(
    conn: UEConnection,
    asset_path: str,
    layout: dict[str, Any],
) -> dict[str, Any]:
    """Build a UMG widget hierarchy from a Python dict via C++ BFWidgetExtensions.

    layout format:
      {"type": "VerticalBox", "name": "Root", "children": [
          {"type": "TextBlock", "name": "TitleText", "text": "Hello", "fontSize": 32},
          {"type": "Button",    "name": "OkBtn",
           "children": [{"type": "TextBlock", "name": "BtnLabel", "text": "OK"}]}
      ]}
    """
    import json as _json
    layout_json = _json.dumps(layout)
    code = f"""
import unreal, json
asset_path  = {json.dumps(asset_path)}
layout_json = {json.dumps(layout_json)}

if not hasattr(unreal, "BFWidgetExtensions"):
    print(json.dumps({{"ok": False, "error": "BFWidgetExtensions not available — build BattleforgeEditor first."}}))
else:
    ok = unreal.BFWidgetExtensions.create_widget_layout(asset_path, layout_json)
    print(json.dumps({{"ok": ok}}))
"""
    return _run_and_parse(conn, code)


def add_property_binding(
    conn: UEConnection,
    asset_path: str,
    widget_name: str,
    property_name: str,
    function_name: str,
) -> dict[str, Any]:
    """Bind a widget property to a Blueprint function via C++ BFWidgetExtensions.

    Equivalent to clicking the Bind button on a widget property in the UMG Designer.
    The function stub must already exist in the Widget Blueprint.
    """
    code = f"""
import unreal, json
asset_path    = {json.dumps(asset_path)}
widget_name   = {json.dumps(widget_name)}
property_name = {json.dumps(property_name)}
function_name = {json.dumps(function_name)}

if not hasattr(unreal, "BFWidgetExtensions"):
    print(json.dumps({{"ok": False, "error": "BFWidgetExtensions not available — build BattleforgeEditor first."}}))
else:
    ok = unreal.BFWidgetExtensions.add_property_binding(asset_path, widget_name, property_name, function_name)
    print(json.dumps({{"ok": ok}}))
"""
    return _run_and_parse(conn, code)


def scaffold_widget(
    conn: UEConnection,
    asset_path: str,
    variables: list[dict[str, str]] | None = None,
    functions: list[str] | None = None,
) -> dict[str, Any]:
    """Create a Widget Blueprint and add all requested variables and functions in one call.

    variables: list of {name, type} dicts
    functions: list of function name strings
    """
    variables = variables or []
    functions = functions or []
    code = f"""
import unreal, json
asset_path = {json.dumps(asset_path)}
variables  = {json.dumps(variables)}
functions  = {json.dumps(functions)}
EAL = unreal.EditorAssetLibrary
BEL = unreal.BlueprintEditorLibrary

_BASIC = {{
    "float":"real","real":"real","double":"real",
    "int":"int","integer":"int",
    "bool":"bool","boolean":"bool",
    "string":"string","str":"string",
    "name":"name","text":"text",
    "object":"object","class":"class",
    "delegate":"delegate","multicast_delegate":"multicast_delegate",
}}

def _pin(ts):
    ts = ts.strip()
    if ts.lower().startswith("array:"):
        return BEL.get_array_type(_pin(ts[6:]))
    lower = ts.lower().replace(" ","").replace("_","")
    # Common structs
    _structs = {{
        "vector": "/Script/CoreUObject.Vector",
        "rotator": "/Script/CoreUObject.Rotator",
        "transform": "/Script/CoreUObject.Transform",
        "timerhandle": "/Script/Engine.TimerHandle",
    }}
    if lower in _structs:
        obj = unreal.find_object(None, _structs[lower])
        return BEL.get_struct_type(obj)
    mapped = _BASIC.get(lower, lower)
    return BEL.get_basic_type_by_name(mapped)

results = {{}}

# Ensure the asset exists
if not EAL.does_asset_exist(asset_path):
    cls = unreal.load_class(None, "/Script/UMG.UserWidget")
    bp  = BEL.create_blueprint_asset_with_parent(asset_path, cls)
    results["created"] = bool(bp)
    if not bp:
        print(json.dumps({{"ok": False, "error": "Failed to create widget blueprint"}}))
        raise SystemExit()
else:
    results["created"] = False

bp = EAL.load_asset(asset_path)

# Add variables
var_results = {{}}
for v in variables:
    vname, vtype = v["name"], v["type"]
    try:
        ok = BEL.add_member_variable(bp, vname, _pin(vtype))
        var_results[vname] = "added" if ok else "already_exists"
    except Exception as e:
        var_results[vname] = f"error:{{e}}"
results["variables"] = var_results

# Add functions
fn_results = {{}}
for fname in functions:
    try:
        g = BEL.add_function_graph(bp, fname)
        fn_results[fname] = "added" if g else "already_exists"
    except Exception as e:
        fn_results[fname] = f"error:{{e}}"
results["functions"] = fn_results

BEL.compile_blueprint(bp)
EAL.save_asset(asset_path)
results["ok"] = True
print(json.dumps(results))
"""
    return _run_and_parse(conn, code)
