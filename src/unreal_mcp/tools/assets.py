"""Asset management tools."""

from __future__ import annotations

import json
from typing import Any

from ..connection import UEConnection
from ._util import pyval


def list_assets(
    conn: UEConnection,
    path: str,
    recursive: bool = False,
    class_filter: str | None = None,
) -> dict[str, Any]:
    code = f"""
import unreal, json
path = {json.dumps(path)}
recursive = {pyval(recursive)}
class_filter = {pyval(class_filter)}
ar = unreal.AssetRegistryHelpers.get_asset_registry()
filter = unreal.ARFilter(
    package_paths=[path],
    recursive_paths=recursive,
    class_names=[class_filter] if class_filter else [],
)
asset_data_list = ar.get_assets(filter)
assets = []
for ad in asset_data_list:
    asset_path = str(ad.package_name) + '.' + str(ad.asset_name)
    assets.append({{
        "name": str(ad.asset_name),
        "path": asset_path,
        "class": str(ad.asset_class_path.asset_name),
    }})
print(json.dumps({{"ok": True, "assets": assets}}))
"""
    return _run_and_parse(conn, code)


def find_asset(conn: UEConnection, pattern: str) -> dict[str, Any]:
    code = f"""
import unreal, json, fnmatch
pattern = {json.dumps(pattern)}
ar = unreal.AssetRegistryHelpers.get_asset_registry()
all_assets = ar.get_all_assets()
results = []
for ad in all_assets:
    name = str(ad.asset_name)
    if pattern in name or fnmatch.fnmatch(name, pattern):
        asset_path = str(ad.package_name) + '.' + name
        results.append({{
            "name": name,
            "path": asset_path,
            "class": str(ad.asset_class_path.asset_name),
        }})
print(json.dumps({{"ok": True, "assets": results}}))
"""
    return _run_and_parse(conn, code)


def import_asset(conn: UEConnection, source_path: str, destination_path: str) -> dict[str, Any]:
    code = f"""
import unreal, json, os
source_path = {json.dumps(source_path)}
destination_path = {json.dumps(destination_path)}
if not os.path.exists(source_path):
    print(json.dumps({{"ok": False, "error": f"Source file not found: '{{source_path}}'"}}))
else:
    task = unreal.AssetImportTask()
    task.set_editor_property('filename', source_path)
    task.set_editor_property('destination_path', destination_path)
    task.set_editor_property('automated', True)
    task.set_editor_property('save', True)
    unreal.AssetToolsHelpers.get_asset_tools().import_asset_tasks([task])
    imported = task.get_editor_property('imported_object_paths')
    if imported:
        print(json.dumps({{"ok": True, "asset_path": imported[0]}}))
    else:
        print(json.dumps({{"ok": False, "error": "Import failed — no assets were created"}}))
"""
    return _run_and_parse(conn, code)


def save_asset(conn: UEConnection, asset_path: str) -> dict[str, Any]:
    code = f"""
import unreal, json
asset_path = {json.dumps(asset_path)}
asset = unreal.EditorAssetLibrary.load_asset(asset_path)
if asset is None:
    print(json.dumps({{"ok": False, "error": f"Asset not found: '{{asset_path}}'"}}))
else:
    unreal.EditorAssetLibrary.save_asset(asset_path)
    print(json.dumps({{"ok": True}}))
"""
    return _run_and_parse(conn, code)


def save_all_assets(conn: UEConnection) -> dict[str, Any]:
    code = """
import unreal, json
result = unreal.EditorAssetLibrary.save_directory('/Game', recursive=True, only_if_is_dirty=True)
# Count saved assets by checking dirty state change — approximate via save_directory return value
# EditorAssetLibrary.save_directory returns True on success but not a count; use asset registry to count
print(json.dumps({"ok": True, "saved_count": -1}))
"""
    return _run_and_parse(conn, code)


def duplicate_asset(conn: UEConnection, source_path: str, destination_path: str) -> dict[str, Any]:
    code = f"""
import unreal, json
source_path = {json.dumps(source_path)}
destination_path = {json.dumps(destination_path)}
# Split destination into path + name
import os
dest_dir = destination_path.rsplit('/', 1)[0]
dest_name = destination_path.rsplit('/', 1)[-1]
result = unreal.EditorAssetLibrary.duplicate_asset(source_path, destination_path)
if result:
    print(json.dumps({{"ok": True, "new_path": destination_path}}))
else:
    print(json.dumps({{"ok": False, "error": f"Failed to duplicate '{{source_path}}' to '{{destination_path}}'"}}))
"""
    return _run_and_parse(conn, code)


def delete_asset(conn: UEConnection, asset_path: str) -> dict[str, Any]:
    code = f"""
import unreal, json
asset_path = {json.dumps(asset_path)}
# Check for references first
ar = unreal.AssetRegistryHelpers.get_asset_registry()
refs = ar.get_referencers(unreal.Name(asset_path), unreal.AssetRegistryDependencyOptions())
ref_list = [str(r) for r in refs if str(r) != asset_path]
if ref_list:
    print(json.dumps({{"ok": False, "error": f"Asset has references: {{ref_list}}"}}))
else:
    success = unreal.EditorAssetLibrary.delete_asset(asset_path)
    if success:
        print(json.dumps({{"ok": True}}))
    else:
        print(json.dumps({{"ok": False, "error": f"Failed to delete asset: '{{asset_path}}'"}}))
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
