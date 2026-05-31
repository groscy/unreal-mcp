"""Tests for blueprint tool snippet generation — no live UE required."""

import json
from unittest.mock import MagicMock

from unreal_mcp.tools import blueprints


def _make_conn(stdout: str = "", ok: bool = True) -> MagicMock:
    conn = MagicMock()
    conn.execute.return_value = {"ok": ok, "stdout": stdout, "result": None, "error": None}
    return conn


class TestCreateBlueprint:
    def test_asset_path_and_parent_in_code(self):
        conn = _make_conn(stdout=json.dumps({"ok": True, "asset_path": "/Game/BP/MyActor"}))
        blueprints.create_blueprint(conn, "/Game/BP/MyActor", "Actor")
        code = conn.execute.call_args[0][0]
        assert "/Game/BP/MyActor" in code
        assert "Actor" in code
        assert "BlueprintFactory" in code

    def test_exists_check_in_code(self):
        conn = _make_conn(stdout=json.dumps({"ok": False, "error": "Asset already exists"}))
        blueprints.create_blueprint(conn, "/Game/BP/MyActor", "Actor")
        code = conn.execute.call_args[0][0]
        assert "does_asset_exist" in code


class TestListBlueprints:
    def test_path_in_code(self):
        conn = _make_conn(stdout=json.dumps({"ok": True, "blueprints": []}))
        blueprints.list_blueprints(conn, "/Game/Blueprints")
        code = conn.execute.call_args[0][0]
        assert "/Game/Blueprints" in code
        assert "Blueprint" in code


class TestCompileBlueprint:
    def test_compile_call_in_code(self):
        conn = _make_conn(stdout=json.dumps({"ok": True, "warnings": []}))
        blueprints.compile_blueprint(conn, "/Game/BP/MyActor")
        code = conn.execute.call_args[0][0]
        assert "compile_blueprint" in code
        assert "/Game/BP/MyActor" in code


class TestAddVariable:
    def test_variable_name_type_in_code(self):
        conn = _make_conn(stdout=json.dumps({"ok": True}))
        blueprints.add_variable(conn, "/Game/BP/MyActor", "Health", "Float")
        code = conn.execute.call_args[0][0]
        assert "Health" in code
        assert "Float" in code
        assert "new_variables" in code

    def test_default_value_in_code(self):
        conn = _make_conn(stdout=json.dumps({"ok": True}))
        blueprints.add_variable(conn, "/Game/BP/MyActor", "MaxHealth", "Float", 100.0)
        code = conn.execute.call_args[0][0]
        assert "100.0" in code


class TestAddFunction:
    def test_function_name_in_code(self):
        conn = _make_conn(stdout=json.dumps({"ok": True}))
        blueprints.add_function(conn, "/Game/BP/MyActor", "OnDeath")
        code = conn.execute.call_args[0][0]
        assert "OnDeath" in code
        assert "add_function_graph_to_blueprint" in code


class TestGetBlueprintInfo:
    def test_info_code_includes_variables_functions_components(self):
        conn = _make_conn(stdout=json.dumps({
            "ok": True,
            "parent_class": "Actor",
            "variables": [],
            "functions": [],
            "components": [],
        }))
        blueprints.get_blueprint_info(conn, "/Game/BP/MyActor")
        code = conn.execute.call_args[0][0]
        assert "new_variables" in code
        assert "function_graphs" in code
        assert "simple_construction_script" in code


class TestCallFunction:
    def test_actor_lookup_in_code(self):
        conn = _make_conn(stdout=json.dumps({"ok": True, "result": None}))
        blueprints.call_function(conn, "MyActor", "OnActivate")
        code = conn.execute.call_args[0][0]
        assert "get_all_level_actors" in code
        assert "OnActivate" in code

    def test_args_in_code(self):
        conn = _make_conn(stdout=json.dumps({"ok": True, "result": None}))
        blueprints.call_function(conn, "MyActor", "SetDamage", {"damage": 50})
        code = conn.execute.call_args[0][0]
        assert "damage" in code
        assert "50" in code
