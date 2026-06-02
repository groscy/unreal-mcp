"""Tests for actor tool snippet generation — no live UE required."""

import json
from unittest.mock import MagicMock

import pytest

from unreal_mcp.tools import actors


def _make_conn(stdout: str = "", ok: bool = True, error: str | None = None) -> MagicMock:
    conn = MagicMock()
    conn.execute.return_value = {"ok": ok, "stdout": stdout, "result": None, "error": error}
    return conn


class TestListActors:
    def test_passes_code_to_execute(self):
        conn = _make_conn(stdout=json.dumps({"ok": True, "actors": []}))
        result = actors.list_actors(conn)
        conn.execute.assert_called_once()
        code = conn.execute.call_args[0][0]
        assert "get_all_level_actors" in code
        assert result == {"ok": True, "actors": []}

    def test_returns_ok_false_on_connection_error(self):
        conn = _make_conn(ok=False, error="not connected")
        result = actors.list_actors(conn)
        assert result["ok"] is False


class TestGetActorProperties:
    def test_label_injected_safely(self):
        conn = _make_conn(stdout=json.dumps({"ok": True, "properties": {}}))
        actors.get_actor_properties(conn, 'My "Actor"')
        code = conn.execute.call_args[0][0]
        assert '"My \\"Actor\\""' in code or "My \\\"Actor\\\"" in code or json.dumps('My "Actor"') in code

    def test_not_found_error(self):
        conn = _make_conn(stdout=json.dumps({"ok": False, "error": "Actor 'X' not found in the current level"}))
        result = actors.get_actor_properties(conn, "X")
        assert result["ok"] is False
        assert "not found" in result["error"]

    def test_uses_dir_for_property_enumeration(self):
        conn = _make_conn(stdout=json.dumps({"ok": True, "properties": {}}))
        actors.get_actor_properties(conn, "SomeActor")
        code = conn.execute.call_args[0][0]
        assert "dir(actor)" in code
        assert "get_editor_property" in code
        assert "get_class().get_properties" not in code


class TestPlaceActor:
    def test_default_transform_in_code(self):
        conn = _make_conn(stdout=json.dumps({"ok": True, "label": "PointLight_0", "name": "PointLight_0"}))
        actors.place_actor(conn, "/Script/Engine.PointLight")
        code = conn.execute.call_args[0][0]
        assert "spawn_actor_from_class" in code

    def test_custom_location_in_code(self):
        conn = _make_conn(stdout=json.dumps({"ok": True, "label": "L", "name": "L"}))
        actors.place_actor(conn, "/Script/Engine.PointLight", location=[100, 200, 300])
        code = conn.execute.call_args[0][0]
        assert "100" in code and "200" in code and "300" in code


class TestDeleteActor:
    def test_label_in_code(self):
        conn = _make_conn(stdout=json.dumps({"ok": True}))
        actors.delete_actor(conn, "MyActor")
        code = conn.execute.call_args[0][0]
        assert "MyActor" in code
        assert "destroy_actor" in code


class TestSetActorTransform:
    def test_partial_update_location_only(self):
        conn = _make_conn(stdout=json.dumps({"ok": True}))
        actors.set_actor_transform(conn, "MyActor", location=[10, 20, 30])
        code = conn.execute.call_args[0][0]
        assert "set_actor_location" in code
        # rotation=None so no set_actor_rotation call expected with values
        assert "rotation = None" in code or '"rotation": null' in code or "rotation = null" in code or "null" in code

    def test_full_transform(self):
        conn = _make_conn(stdout=json.dumps({"ok": True}))
        actors.set_actor_transform(conn, "MyActor", [0, 0, 0], [0, 0, 0], [1, 1, 1])
        code = conn.execute.call_args[0][0]
        assert "set_actor_location" in code
        assert "set_actor_rotation" in code
        assert "set_actor_scale3d" in code


class TestSetActorProperty:
    def test_property_path_and_value_in_code(self):
        conn = _make_conn(stdout=json.dumps({"ok": True}))
        actors.set_actor_property(conn, "MyActor", "LightComponent.Intensity", 5000)
        code = conn.execute.call_args[0][0]
        assert "LightComponent.Intensity" in code
        assert "5000" in code
        assert "set_editor_property" in code
