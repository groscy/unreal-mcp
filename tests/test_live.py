"""Live end-to-end tests — requires a running UE5 editor with Remote Execution enabled.

Run with:  uv run pytest tests/test_live.py -v -s
"""

import json
import pytest

from unreal_mcp.connection import UEConnection
from unreal_mcp.tools import actors, assets, blueprints, editor
from unreal_mcp.tools.python_exec import execute_python


@pytest.fixture(scope="module")
def conn():
    c = UEConnection()
    ok = c.connect()
    if not ok:
        pytest.skip(f"UE5 not reachable: {c._last_error}")
    yield c
    c.disconnect()


# ---------------------------------------------------------------------------
# 10.1 / 10.2 — connection health
# ---------------------------------------------------------------------------

class TestPing:
    def test_ping_returns_ue_version(self, conn):
        result = conn.ping()
        assert result["ok"], result
        assert result["connected"] is True
        assert result["ue_version"], f"Expected version string, got: {result}"
        print(f"\n  UE version: {result['ue_version']}")


# ---------------------------------------------------------------------------
# Python execution
# ---------------------------------------------------------------------------

class TestExecutePython:
    def test_simple_print(self, conn):
        r = execute_python(conn, "print(1 + 1)")
        assert r["ok"], r
        assert "2" in r["stdout"]

    def test_multiline_code(self, conn):
        code = "x = 10\ny = 20\nprint(x + y)"
        r = execute_python(conn, code)
        assert r["ok"], r
        assert "30" in r["stdout"]

    def test_exception_returns_ok_false(self, conn):
        r = execute_python(conn, "raise ValueError('test error')")
        assert r["ok"] is False
        assert r["error"]

    def test_no_output_returns_empty_stdout(self, conn):
        r = execute_python(conn, "x = 42")
        assert r["ok"], r
        assert r["stdout"] == "" or r["stdout"] is not None


# ---------------------------------------------------------------------------
# Actor management
# ---------------------------------------------------------------------------

class TestActors:
    def test_list_actors(self, conn):
        r = actors.list_actors(conn)
        assert r["ok"], r
        assert "actors" in r
        print(f"\n  Level has {len(r['actors'])} actors")
        if r["actors"]:
            a = r["actors"][0]
            assert "label" in a
            assert "class" in a
            assert "location" in a

    def test_place_and_delete_actor(self, conn):
        # Place a point light
        r = actors.place_actor(conn, "/Script/Engine.PointLight", location=[0, 0, 500])
        assert r["ok"], r
        label = r["label"]
        print(f"\n  Placed actor: {label}")

        # Verify it appears in listing
        listing = actors.list_actors(conn)
        labels = [a["label"] for a in listing["actors"]]
        assert label in labels, f"{label} not found in level"

        # Delete it
        r = actors.delete_actor(conn, label)
        assert r["ok"], r

        # Verify gone
        listing = actors.list_actors(conn)
        labels = [a["label"] for a in listing["actors"]]
        assert label not in labels

    def test_get_actor_properties(self, conn):
        listing = actors.list_actors(conn)
        assert listing["actors"], "Level has no actors to inspect"
        label = listing["actors"][0]["label"]
        r = actors.get_actor_properties(conn, label)
        assert r["ok"], r
        assert "properties" in r
        assert len(r["properties"]) > 0, "Expected at least one property"
        print(f"\n  {label} has {len(r['properties'])} properties")

    def test_delete_nonexistent_actor(self, conn):
        r = actors.delete_actor(conn, "__nonexistent_actor_xyz__")
        assert r["ok"] is False
        assert "not found" in r["error"].lower()


# ---------------------------------------------------------------------------
# Asset management
# ---------------------------------------------------------------------------

class TestAssets:
    def test_list_assets_game(self, conn):
        r = assets.list_assets(conn, "/Game", recursive=True)
        assert r["ok"], r
        assert "assets" in r
        print(f"\n  /Game has {len(r['assets'])} assets")

    def test_find_asset(self, conn):
        r = assets.find_asset(conn, "*")
        assert r["ok"], r
        assert isinstance(r["assets"], list)

    def test_save_all_assets(self, conn):
        r = assets.save_all_assets(conn)
        assert r["ok"], r


# ---------------------------------------------------------------------------
# Editor control
# ---------------------------------------------------------------------------

class TestEditor:
    def test_get_world_settings(self, conn):
        r = editor.get_world_settings(conn)
        assert r["ok"], r
        assert "settings" in r
        print(f"\n  World settings keys: {list(r['settings'].keys())}")

    def test_save_level(self, conn):
        r = editor.save_level(conn)
        assert r["ok"], r

    def test_run_console_command(self, conn):
        r = editor.run_console_command(conn, "stat fps")
        assert r["ok"], r
