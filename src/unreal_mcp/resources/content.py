"""unreal://content/tree resource — live content browser tree."""

from __future__ import annotations

import json
from typing import Any

from ..connection import UEConnection

_CODE = """
import unreal, json

def build_tree(path):
    ar = unreal.AssetRegistryHelpers.get_asset_registry()
    sub_paths = ar.get_sub_paths(path, recurse=False)
    filter = unreal.ARFilter(package_paths=[path], recursive_paths=False)
    asset_data_list = ar.get_assets(filter)
    assets = [
        {"name": str(ad.asset_name), "path": str(ad.object_path), "class": str(ad.asset_class_path.asset_name)}
        for ad in asset_data_list
    ]
    children = [build_tree(str(p)) for p in sub_paths]
    return {"path": path, "assets": assets, "children": children}

tree = build_tree('/Game')
print(json.dumps(tree))
"""


def get_tree(conn: UEConnection) -> dict[str, Any]:
    result = conn.execute(_CODE)
    if not result["ok"]:
        return {"path": "/Game", "assets": [], "children": []}
    stdout = (result.get("stdout") or "").strip()
    if stdout:
        try:
            return json.loads(stdout)
        except json.JSONDecodeError:
            pass
    return {"path": "/Game", "assets": [], "children": []}
