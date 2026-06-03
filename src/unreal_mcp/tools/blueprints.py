"""Blueprint management tools — UE 5.7 compatible."""

from __future__ import annotations

import json
from typing import Any

from ..connection import UEConnection
from ._util import pyval

# ---------------------------------------------------------------------------
# Helpers shared across snippets
# ---------------------------------------------------------------------------

_BEL_SETUP = """
import unreal
EAL = unreal.EditorAssetLibrary
BEL = unreal.BlueprintEditorLibrary

def _pin_for(type_str):
    \"\"\"Return an EdGraphPinType for a human-readable type string.
    Supports: bool, int, float, string, name, text, object, class,
              delegate, multicast_delegate, vector, rotator, transform,
              array:<inner>, struct:<path>
    \"\"\"
    ts = type_str.strip()
    # Array wrapper
    if ts.lower().startswith("array:"):
        inner = _pin_for(ts[6:])
        return BEL.get_array_type(inner)
    # Struct by path
    if ts.lower().startswith("struct:"):
        obj = unreal.find_object(None, ts[7:])
        if obj is None:
            raise ValueError(f"Struct not found: {ts[7:]}")
        return BEL.get_struct_type(obj)
    # Well-known structs
    _STRUCT_PATHS = {
        "vector":    "/Script/CoreUObject.Vector",
        "rotator":   "/Script/CoreUObject.Rotator",
        "transform": "/Script/CoreUObject.Transform",
        "timerhandle": "/Script/Engine.TimerHandle",
        "color":     "/Script/CoreUObject.LinearColor",
    }
    lower = ts.lower().replace(" ", "")
    if lower in _STRUCT_PATHS:
        obj = unreal.find_object(None, _STRUCT_PATHS[lower])
        if obj:
            return BEL.get_struct_type(obj)
    # Basic types
    _BASIC = {
        "float": "real", "double": "real", "real": "real",
        "int": "int", "integer": "int", "int32": "int",
        "bool": "bool", "boolean": "bool",
        "string": "string", "str": "string",
        "name": "name",
        "text": "text",
        "object": "object",
        "class": "class",
        "delegate": "delegate",
        "multicast_delegate": "multicast_delegate",
        "multicastdelegate": "multicast_delegate",
        "event_dispatcher": "multicast_delegate",
    }
    mapped = _BASIC.get(lower, lower)
    return BEL.get_basic_type_by_name(mapped)
"""


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


# ---------------------------------------------------------------------------
# Blueprint CRUD
# ---------------------------------------------------------------------------

def create_blueprint(conn: UEConnection, asset_path: str, parent_class: str) -> dict[str, Any]:
    code = f"""
import unreal, json
asset_path = {json.dumps(asset_path)}
parent_class_name = {json.dumps(parent_class)}
EAL = unreal.EditorAssetLibrary
BEL = unreal.BlueprintEditorLibrary

if EAL.does_asset_exist(asset_path):
    print(json.dumps({{"ok": False, "error": f"Asset already exists: '{{asset_path}}'"}}))
else:
    # Try /Script/Engine.<Name> first, then bare path
    parent_cls = (unreal.load_class(None, f'/Script/Engine.{{parent_class_name}}')
                  or unreal.load_class(None, parent_class_name))
    if parent_cls is None:
        print(json.dumps({{"ok": False, "error": f"Parent class '{{parent_class_name}}' not found"}}))
    else:
        bp = BEL.create_blueprint_asset_with_parent(asset_path, parent_cls)
        if bp is None:
            print(json.dumps({{"ok": False, "error": "Blueprint creation failed"}}))
        else:
            EAL.save_asset(asset_path)
            print(json.dumps({{"ok": True, "asset_path": asset_path}}))
"""
    return _run_and_parse(conn, code)


def list_blueprints(conn: UEConnection, path: str, recursive: bool = True) -> dict[str, Any]:
    code = f"""
import unreal, json
path = {json.dumps(path)}
recursive = {pyval(recursive)}
EAL = unreal.EditorAssetLibrary
BEL = unreal.BlueprintEditorLibrary

ar = unreal.AssetRegistryHelpers.get_asset_registry()
filter_ = unreal.ARFilter(
    package_paths=[path],
    recursive_paths=recursive,
    class_names=["Blueprint", "WidgetBlueprint"],
)
results = []
for ad in ar.get_assets(filter_):
    bp = EAL.load_asset(str(ad.package_name))
    parent = ""
    if bp:
        gen = BEL.generated_class(bp)
        if gen:
            sup = gen.get_super_class()
            if sup:
                parent = sup.get_name()
    results.append({{"name": str(ad.asset_name), "path": str(ad.package_name), "parent_class": parent}})
print(json.dumps({{"ok": True, "blueprints": results}}))
"""
    return _run_and_parse(conn, code)


def compile_blueprint(conn: UEConnection, asset_path: str) -> dict[str, Any]:
    code = f"""
import unreal, json
asset_path = {json.dumps(asset_path)}
EAL = unreal.EditorAssetLibrary
BEL = unreal.BlueprintEditorLibrary

bp = EAL.load_asset(asset_path)
if bp is None:
    print(json.dumps({{"ok": False, "error": f"Not found: {{asset_path}}"}}))
else:
    try:
        BEL.compile_blueprint(bp)
        EAL.save_asset(asset_path)
        print(json.dumps({{"ok": True}}))
    except Exception as e:
        print(json.dumps({{"ok": False, "error": str(e)}}))
"""
    return _run_and_parse(conn, code)


# ---------------------------------------------------------------------------
# Blueprint info
# ---------------------------------------------------------------------------

def get_blueprint_info(conn: UEConnection, asset_path: str) -> dict[str, Any]:
    code = f"""
import unreal, json
asset_path = {json.dumps(asset_path)}
EAL = unreal.EditorAssetLibrary
BEL = unreal.BlueprintEditorLibrary

bp = EAL.load_asset(asset_path)
if bp is None:
    print(json.dumps({{"ok": False, "error": f"Not found: {{asset_path}}"}}))
else:
    info = {{"ok": True, "parent_class": "", "variables": [], "functions": [], "event_dispatchers": [], "components": []}}

    # Parent class via AssetRegistry metadata tag (UE 5.7 compatible)
    try:
        ar   = unreal.AssetRegistryHelpers.get_asset_registry()
        name = asset_path.rsplit("/", 1)[-1]
        data = ar.get_asset_by_object_path(f"{{asset_path}}.{{name}}")
        if data:
            pc = data.get_tag_value("ParentClass")
            if pc:
                info["parent_class"] = pc.rsplit(".", 1)[-1].rstrip("'")
    except Exception:
        pass

    # Variables / functions / dispatchers — best effort (property not exposed in UE 5.7)
    try:
        for v in bp.get_editor_property("new_variables"):
            vname = str(v.var_name)
            vtype = ""
            try:
                vtype = str(v.var_type.get_editor_property("PinCategory"))
            except Exception:
                pass
            if "delegate" in vtype.lower():
                info["event_dispatchers"].append(vname)
            else:
                info["variables"].append({{"name": vname, "type": vtype}})
    except Exception:
        pass

    try:
        for g in bp.get_editor_property("function_graphs"):
            info["functions"].append(g.get_name())
    except Exception:
        pass

    # Components via SCS (best effort)
    try:
        scs = bp.get_editor_property("simple_construction_script")
        if scs:
            for node in scs.get_all_nodes():
                comp = node.component_template
                if comp:
                    info["components"].append({{
                        "name": str(node.variable_name),
                        "class": comp.get_class().get_name(),
                    }})
    except Exception:
        pass

    print(json.dumps(info))
"""
    return _run_and_parse(conn, code)


# ---------------------------------------------------------------------------
# Variables
# ---------------------------------------------------------------------------

def add_variable(
    conn: UEConnection,
    asset_path: str,
    name: str,
    var_type: str,
    default_value: Any = None,
) -> dict[str, Any]:
    code = f"""
import unreal, json
asset_path = {json.dumps(asset_path)}
var_name   = {json.dumps(name)}
var_type   = {json.dumps(var_type)}
default_value = {json.dumps(default_value)}
EAL = unreal.EditorAssetLibrary
BEL = unreal.BlueprintEditorLibrary

{_BEL_SETUP}

bp = EAL.load_asset(asset_path)
if bp is None:
    print(json.dumps({{"ok": False, "error": f"Not found: {{asset_path}}"}}))
else:
    try:
        pin_type = _pin_for(var_type)
        ok = BEL.add_member_variable(bp, var_name, pin_type)
        if not ok:
            print(json.dumps({{"ok": False, "error": f"Variable '{{var_name}}' already exists or could not be created"}}))
        else:
            # Optionally set default value via CDO
            if default_value is not None:
                try:
                    gen = BEL.generated_class(bp)
                    if gen:
                        cdo = gen.get_default_object()
                        if cdo:
                            cdo.set_editor_property(var_name, default_value)
                except Exception:
                    pass
            BEL.compile_blueprint(bp)
            EAL.save_asset(asset_path)
            print(json.dumps({{"ok": True}}))
    except Exception as e:
        import traceback
        print(json.dumps({{"ok": False, "error": str(e), "detail": traceback.format_exc()}}))
"""
    return _run_and_parse(conn, code)


def set_variable_default(
    conn: UEConnection,
    asset_path: str,
    name: str,
    value: Any,
) -> dict[str, Any]:
    """Set a default value on a Blueprint variable.

    Works for variables inherited from C++ parent classes (e.g. float properties
    on Character/Actor subclasses). Blueprint-defined variables are not accessible
    via Python CDO in UE 5.7 and will return an informative error.
    """
    code = f"""
import unreal, json
asset_path = {json.dumps(asset_path)}
var_name   = {json.dumps(name)}
value      = {json.dumps(value)}
EAL = unreal.EditorAssetLibrary
BEL = unreal.BlueprintEditorLibrary

bp = EAL.load_asset(asset_path)
if bp is None:
    print(json.dumps({{"ok": False, "error": f"Not found: {{asset_path}}"}}))
else:
    gen = BEL.generated_class(bp)
    cdo = gen.get_default_object() if gen else None
    if cdo is None:
        print(json.dumps({{"ok": False, "error": "Could not get CDO"}}))
    else:
        try:
            cdo.set_editor_property(var_name, value)
            EAL.save_asset(asset_path)
            print(json.dumps({{"ok": True}}))
        except Exception as e:
            print(json.dumps({{
                "ok": False,
                "error": str(e),
                "hint": "Blueprint-defined variables are not accessible via Python CDO in UE 5.7. "
                        "Set the default in the Blueprint Class Defaults panel instead.",
            }}))
"""
    return _run_and_parse(conn, code)


# ---------------------------------------------------------------------------
# Functions & event dispatchers
# ---------------------------------------------------------------------------

def add_function(conn: UEConnection, asset_path: str, name: str) -> dict[str, Any]:
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
            print(json.dumps({{"ok": False, "error": f"Function '{{func_name}}' already exists or could not be created"}}))
        else:
            EAL.save_asset(asset_path)
            print(json.dumps({{"ok": True}}))
    except Exception as e:
        print(json.dumps({{"ok": False, "error": str(e)}}))
"""
    return _run_and_parse(conn, code)


def add_event_dispatcher(
    conn: UEConnection,
    asset_path: str,
    name: str,
) -> dict[str, Any]:
    """Add a multicast delegate (Event Dispatcher) to a Blueprint."""
    code = f"""
import unreal, json
asset_path = {json.dumps(asset_path)}
disp_name  = {json.dumps(name)}
EAL = unreal.EditorAssetLibrary
BEL = unreal.BlueprintEditorLibrary

bp = EAL.load_asset(asset_path)
if bp is None:
    print(json.dumps({{"ok": False, "error": f"Not found: {{asset_path}}"}}))
else:
    try:
        pin_type = BEL.get_basic_type_by_name("multicast_delegate")
        ok = BEL.add_member_variable(bp, disp_name, pin_type)
        if not ok:
            print(json.dumps({{"ok": False, "error": f"Dispatcher '{{disp_name}}' already exists or failed"}}))
        else:
            BEL.compile_blueprint(bp)
            EAL.save_asset(asset_path)
            print(json.dumps({{"ok": True}}))
    except Exception as e:
        print(json.dumps({{"ok": False, "error": str(e)}}))
"""
    return _run_and_parse(conn, code)


# ---------------------------------------------------------------------------
# Components
# ---------------------------------------------------------------------------

def add_component(
    conn: UEConnection,
    asset_path: str,
    component_class: str,
    variable_name: str,
) -> dict[str, Any]:
    """Add a component to a Blueprint's SCS. Requires UE Python to expose SimpleConstructionScript."""
    code = f"""
import unreal, json
asset_path     = {json.dumps(asset_path)}
comp_class_str = {json.dumps(component_class)}
variable_name  = {json.dumps(variable_name)}
EAL = unreal.EditorAssetLibrary
BEL = unreal.BlueprintEditorLibrary

bp = EAL.load_asset(asset_path)
if bp is None:
    print(json.dumps({{"ok": False, "error": f"Not found: {{asset_path}}"}}))
    raise SystemExit()

comp_cls = (unreal.load_class(None, f"/Script/Engine.{{comp_class_str}}")
            or unreal.load_class(None, comp_class_str))
if comp_cls is None:
    print(json.dumps({{"ok": False, "error": f"Component class not found: {{comp_class_str}}"}}))
    raise SystemExit()

errors = []

# Method: use unreal.EditorBlueprintLibrary.add_component if it exists (future-proofing)
if hasattr(unreal, "EditorBlueprintLibrary"):
    try:
        lib = unreal.EditorBlueprintLibrary
        if hasattr(lib, "add_component_to_blueprint"):
            lib.add_component_to_blueprint(bp, comp_cls, variable_name)
            BEL.compile_blueprint(bp)
            EAL.save_asset(asset_path)
            print(json.dumps({{"ok": True, "method": "EditorBlueprintLibrary"}}))
            raise SystemExit()
    except SystemExit:
        raise
    except Exception as e:
        errors.append(f"EditorBlueprintLibrary: {{e}}")

# UE 5.7: SimpleConstructionScript not accessible via Python API.
# Component addition requires the Blueprint Components panel in the editor.
print(json.dumps({{
    "ok": False,
    "error": "add_component is not supported in UE 5.7 via Python API (SimpleConstructionScript is not exposed). Add the component manually in the Blueprint Components panel.",
    "component_class": comp_class_str,
    "variable_name": variable_name,
    "errors": errors,
}}))
"""
    return _run_and_parse(conn, code)


# ---------------------------------------------------------------------------
# call_function (unchanged logic, updated to use EAL)
# ---------------------------------------------------------------------------

def add_component_cpp(
    conn: UEConnection,
    asset_path: str,
    component_class: str,
    variable_name: str,
) -> dict[str, Any]:
    """Add a component via the C++ BFEditorExtensions (requires BattleforgeEditor module built)."""
    code = f"""
import unreal, json
asset_path     = {json.dumps(asset_path)}
comp_class     = {json.dumps(component_class)}
variable_name  = {json.dumps(variable_name)}

if not hasattr(unreal, "BFEditorExtensions"):
    print(json.dumps({{"ok": False, "error": "BFEditorExtensions not available — build the BattleforgeEditor C++ module first."}}))
else:
    ok = unreal.BFEditorExtensions.add_component_to_blueprint(asset_path, comp_class, variable_name)
    print(json.dumps({{"ok": ok}}))
"""
    return _run_and_parse(conn, code)


def set_variable_default_cpp(
    conn: UEConnection,
    asset_path: str,
    name: str,
    value: Any,
    value_type: str = "float",
) -> dict[str, Any]:
    """Set a Blueprint variable default via C++ BFEditorExtensions."""
    code = f"""
import unreal, json
asset_path = {json.dumps(asset_path)}
var_name   = {json.dumps(name)}
value      = {json.dumps(value)}
value_type = {json.dumps(value_type)}

if not hasattr(unreal, "BFEditorExtensions"):
    print(json.dumps({{"ok": False, "error": "BFEditorExtensions not available — build BattleforgeEditor first."}}))
else:
    ext = unreal.BFEditorExtensions
    t = value_type.lower()
    if t in ("float", "real", "double"):
        ok = ext.set_variable_default_float(asset_path, var_name, float(value))
    elif t in ("int", "integer", "int32"):
        ok = ext.set_variable_default_int(asset_path, var_name, int(value))
    elif t in ("bool", "boolean"):
        ok = ext.set_variable_default_bool(asset_path, var_name, bool(value))
    else:
        print(json.dumps({{"ok": False, "error": f"Unsupported type: {{value_type}}. Use float/int/bool."}}))
        ok = False
    if ok is not False:
        print(json.dumps({{"ok": ok}}))
"""
    return _run_and_parse(conn, code)


def call_function(
    conn: UEConnection,
    target: str,
    function_name: str,
    args: dict[str, Any] | None = None,
) -> dict[str, Any]:
    args = args or {}
    code = f"""
import unreal, json
target        = {json.dumps(target)}
function_name = {json.dumps(function_name)}
call_args     = {json.dumps(args)}

actor = None
for a in unreal.EditorLevelLibrary.get_all_level_actors():
    if a.get_actor_label() == target:
        actor = a
        break

if actor is not None:
    obj = actor
else:
    bp  = unreal.EditorAssetLibrary.load_asset(target)
    gen = unreal.BlueprintEditorLibrary.generated_class(bp) if bp else None
    obj = gen.get_default_object() if gen else None

if obj is None:
    print(json.dumps({{"ok": False, "error": f"Target '{{target}}' not found"}}))
else:
    func = getattr(obj, function_name, None)
    if func is None:
        print(json.dumps({{"ok": False, "error": f"Function '{{function_name}}' not found"}}))
    else:
        try:
            result = func(**call_args)
            print(json.dumps({{"ok": True, "result": str(result)}}))
        except Exception as e:
            print(json.dumps({{"ok": False, "error": str(e)}}))
"""
    return _run_and_parse(conn, code)
