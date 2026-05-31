"""Blueprint management tools."""

from __future__ import annotations

import json
from typing import Any

from ..connection import UEConnection
from ._util import pyval


def create_blueprint(conn: UEConnection, asset_path: str, parent_class: str) -> dict[str, Any]:
    code = f"""
import unreal, json
asset_path = {json.dumps(asset_path)}
parent_class_name = {json.dumps(parent_class)}

if unreal.EditorAssetLibrary.does_asset_exist(asset_path):
    print(json.dumps({{"ok": False, "error": f"Asset already exists at '{{asset_path}}'"}}))
else:
    parent_cls = unreal.load_class(None, f'/Script/Engine.{{parent_class_name}}')
    if parent_cls is None:
        parent_cls = unreal.load_class(None, parent_class_name)
    if parent_cls is None:
        print(json.dumps({{"ok": False, "error": f"Parent class '{{parent_class_name}}' not found"}}))
    else:
        factory = unreal.BlueprintFactory()
        factory.set_editor_property('parent_class', parent_cls)
        path_parts = asset_path.rsplit('/', 1)
        pkg_path = path_parts[0]
        asset_name = path_parts[1]
        bp = unreal.AssetToolsHelpers.get_asset_tools().create_asset(
            asset_name, pkg_path, unreal.Blueprint, factory
        )
        if bp is None:
            print(json.dumps({{"ok": False, "error": "Blueprint creation failed"}}))
        else:
            unreal.EditorAssetLibrary.save_asset(asset_path)
            print(json.dumps({{"ok": True, "asset_path": asset_path}}))
"""
    return _run_and_parse(conn, code)


def list_blueprints(conn: UEConnection, path: str, recursive: bool = True) -> dict[str, Any]:
    code = f"""
import unreal, json
path = {json.dumps(path)}
recursive = {pyval(recursive)}
ar = unreal.AssetRegistryHelpers.get_asset_registry()
filter = unreal.ARFilter(
    package_paths=[path],
    recursive_paths=recursive,
    class_names=['Blueprint'],
)
asset_data_list = ar.get_assets(filter)
blueprints = []
for ad in asset_data_list:
    asset_path = str(ad.package_name) + '.' + str(ad.asset_name)
    bp = unreal.EditorAssetLibrary.load_asset(str(ad.package_name))
    parent_name = ''
    if bp and hasattr(bp, 'parent_class') and bp.parent_class:
        parent_name = bp.parent_class.get_name()
    blueprints.append({{
        "name": str(ad.asset_name),
        "path": asset_path,
        "parent_class": parent_name,
    }})
print(json.dumps({{"ok": True, "blueprints": blueprints}}))
"""
    return _run_and_parse(conn, code)


def compile_blueprint(conn: UEConnection, asset_path: str) -> dict[str, Any]:
    code = f"""
import unreal, json
asset_path = {json.dumps(asset_path)}
bp = unreal.EditorAssetLibrary.load_asset(asset_path)
if bp is None or not isinstance(bp, unreal.Blueprint):
    print(json.dumps({{"ok": False, "error": f"Blueprint not found: '{{asset_path}}'"}}))
else:
    result = unreal.KismetEditorUtilities.compile_blueprint(bp)
    errors = [str(e) for e in (result.errors if hasattr(result, 'errors') else [])]
    warnings = [str(w) for w in (result.warnings if hasattr(result, 'warnings') else [])]
    if errors:
        print(json.dumps({{"ok": False, "errors": errors, "warnings": warnings}}))
    else:
        print(json.dumps({{"ok": True, "warnings": warnings}}))
"""
    return _run_and_parse(conn, code)


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
var_name = {json.dumps(name)}
var_type = {json.dumps(var_type)}
default_value = {json.dumps(default_value)}

bp = unreal.EditorAssetLibrary.load_asset(asset_path)
if bp is None:
    print(json.dumps({{"ok": False, "error": f"Blueprint not found: '{{asset_path}}'"}}))
else:
    # Check for existing variable
    existing = [v.var_name for v in bp.get_editor_property('new_variables')]
    if var_name in existing:
        print(json.dumps({{"ok": False, "error": f"Variable '{{var_name}}' already exists in blueprint"}}))
    else:
        new_var = unreal.BPVariableDescription()
        new_var.var_name = var_name
        # Map simple type names to FEdGraphPinType
        type_map = {{
            'Float': 'real', 'Boolean': 'bool', 'Integer': 'int',
            'String': 'string', 'Vector': 'struct', 'Object': 'object',
        }}
        pin_cat = type_map.get(var_type, var_type.lower())
        new_var.var_type = unreal.EdGraphPinType(pin_cat, '', None, unreal.EPinContainerType.NONE, False, unreal.EdGraphTerminalType())
        variables = list(bp.get_editor_property('new_variables'))
        variables.append(new_var)
        bp.set_editor_property('new_variables', variables)
        unreal.EditorAssetLibrary.save_asset(asset_path)
        print(json.dumps({{"ok": True}}))
"""
    return _run_and_parse(conn, code)


def add_function(conn: UEConnection, asset_path: str, name: str) -> dict[str, Any]:
    code = f"""
import unreal, json
asset_path = {json.dumps(asset_path)}
func_name = {json.dumps(name)}
bp = unreal.EditorAssetLibrary.load_asset(asset_path)
if bp is None:
    print(json.dumps({{"ok": False, "error": f"Blueprint not found: '{{asset_path}}'"}}))
else:
    graph = unreal.KismetEditorUtilities.add_function_graph_to_blueprint(bp, func_name)
    if graph is None:
        print(json.dumps({{"ok": False, "error": f"Failed to create function '{{func_name}}'"}}))
    else:
        unreal.EditorAssetLibrary.save_asset(asset_path)
        print(json.dumps({{"ok": True}}))
"""
    return _run_and_parse(conn, code)


def get_blueprint_info(conn: UEConnection, asset_path: str) -> dict[str, Any]:
    code = f"""
import unreal, json
asset_path = {json.dumps(asset_path)}
bp = unreal.EditorAssetLibrary.load_asset(asset_path)
if bp is None:
    print(json.dumps({{"ok": False, "error": f"Blueprint not found: '{{asset_path}}'"}}))
else:
    parent_name = bp.parent_class.get_name() if bp.parent_class else ''
    variables = [v.var_name for v in bp.get_editor_property('new_variables')]
    graphs = bp.get_editor_property('function_graphs')
    functions = [g.get_name() for g in graphs]
    # Component hierarchy via SCS
    comps = []
    scs = bp.get_editor_property('simple_construction_script')
    if scs:
        for node in scs.get_all_nodes():
            comp = node.component_template
            if comp:
                comps.append({{"name": node.variable_name, "class": comp.get_class().get_name()}})
    print(json.dumps({{
        "ok": True,
        "parent_class": parent_name,
        "variables": variables,
        "functions": functions,
        "components": comps,
    }}))
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
target = {json.dumps(target)}
function_name = {json.dumps(function_name)}
call_args = {json.dumps(args)}

# Try to find as level actor first
actor = None
for a in unreal.EditorLevelLibrary.get_all_level_actors():
    if a.get_actor_label() == target:
        actor = a
        break

if actor is not None:
    obj = actor
else:
    # Try as Blueprint CDO
    bp = unreal.EditorAssetLibrary.load_asset(target)
    obj = unreal.get_default_object(bp.generated_class()) if bp and hasattr(bp, 'generated_class') else None

if obj is None:
    print(json.dumps({{"ok": False, "error": f"Target '{{target}}' not found"}}))
else:
    func = getattr(obj, function_name, None)
    if func is None:
        print(json.dumps({{"ok": False, "error": f"Function '{{function_name}}' not found on target"}}))
    else:
        try:
            result = func(**call_args)
            print(json.dumps({{"ok": True, "result": result}}))
        except Exception as e:
            print(json.dumps({{"ok": False, "error": str(e)}}))
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
