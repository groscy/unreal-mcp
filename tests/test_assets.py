"""Tests for asset tool snippet generation — no live UE required."""

import json
from unittest.mock import MagicMock

from unreal_mcp.tools import assets


def _make_conn(stdout: str = "", ok: bool = True) -> MagicMock:
    conn = MagicMock()
    conn.execute.return_value = {"ok": ok, "stdout": stdout, "result": None, "error": None}
    return conn


class TestListAssets:
    def test_path_in_code(self):
        conn = _make_conn(stdout=json.dumps({"ok": True, "assets": []}))
        assets.list_assets(conn, "/Game/Meshes")
        code = conn.execute.call_args[0][0]
        assert "/Game/Meshes" in code
        assert "AssetRegistryHelpers" in code

    def test_recursive_flag(self):
        conn = _make_conn(stdout=json.dumps({"ok": True, "assets": []}))
        assets.list_assets(conn, "/Game", recursive=True)
        code = conn.execute.call_args[0][0]
        assert "true" in code.lower() or "True" in code

    def test_class_filter(self):
        conn = _make_conn(stdout=json.dumps({"ok": True, "assets": []}))
        assets.list_assets(conn, "/Game", class_filter="StaticMesh")
        code = conn.execute.call_args[0][0]
        assert "StaticMesh" in code


class TestFindAsset:
    def test_pattern_in_code(self):
        conn = _make_conn(stdout=json.dumps({"ok": True, "assets": []}))
        assets.find_asset(conn, "SM_Rock*")
        code = conn.execute.call_args[0][0]
        assert "SM_Rock*" in code
        assert "fnmatch" in code


class TestImportAsset:
    def test_source_and_dest_in_code(self):
        conn = _make_conn(stdout=json.dumps({"ok": True, "asset_path": "/Game/Imported/Texture"}))
        assets.import_asset(conn, "C:/art/texture.png", "/Game/Imported")
        code = conn.execute.call_args[0][0]
        assert "C:/art/texture.png" in code
        assert "/Game/Imported" in code
        assert "AssetImportTask" in code

    def test_missing_source_check_in_code(self):
        conn = _make_conn(stdout=json.dumps({"ok": True, "asset_path": "/Game/x"}))
        assets.import_asset(conn, "/missing/file.png", "/Game/Dest")
        code = conn.execute.call_args[0][0]
        assert "os.path.exists" in code


class TestSaveAsset:
    def test_asset_path_in_code(self):
        conn = _make_conn(stdout=json.dumps({"ok": True}))
        assets.save_asset(conn, "/Game/Materials/Mat_Red")
        code = conn.execute.call_args[0][0]
        assert "/Game/Materials/Mat_Red" in code
        assert "save_asset" in code


class TestSaveAllAssets:
    def test_save_directory_in_code(self):
        conn = _make_conn(stdout=json.dumps({"ok": True, "saved_count": -1}))
        assets.save_all_assets(conn)
        code = conn.execute.call_args[0][0]
        assert "save_directory" in code


class TestDuplicateAsset:
    def test_source_and_dest_in_code(self):
        conn = _make_conn(stdout=json.dumps({"ok": True, "new_path": "/Game/Materials/Mat_Red_Copy"}))
        assets.duplicate_asset(conn, "/Game/Materials/Mat_Red", "/Game/Materials/Mat_Red_Copy")
        code = conn.execute.call_args[0][0]
        assert "duplicate_asset" in code
        assert "/Game/Materials/Mat_Red" in code


class TestDeleteAsset:
    def test_reference_check_in_code(self):
        conn = _make_conn(stdout=json.dumps({"ok": True}))
        assets.delete_asset(conn, "/Game/Materials/Mat_Red")
        code = conn.execute.call_args[0][0]
        assert "get_referencers" in code
        assert "delete_asset" in code
