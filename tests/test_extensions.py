"""Tests for the optional editor-extension contract — no live UE required."""

import json
from unittest.mock import MagicMock

import pytest

from unreal_mcp import extensions
from unreal_mcp.extensions import ROLE_BLUEPRINT, ROLE_WIDGET


@pytest.fixture(autouse=True)
def _clear_cache_and_env(monkeypatch):
    """Each test starts with no cached probe and no configured override."""
    monkeypatch.delenv("UE_EDITOR_EXTENSIONS", raising=False)
    extensions.reset_cache()
    yield
    extensions.reset_cache()


def _make_conn(available_classes, epoch=1, ok=True, raises=None, stdout=None):
    """A connection whose editor exposes `available_classes`."""
    conn = MagicMock()
    conn.epoch = epoch
    if raises is not None:
        conn.execute.side_effect = raises
        return conn
    if stdout is None:
        stdout = json.dumps({"available": list(available_classes)})
    conn.execute.return_value = {"ok": ok, "stdout": stdout, "result": None, "error": None}
    return conn


# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------

class TestConfiguredRoles:
    def test_defaults_when_unset(self):
        roles = extensions.configured_roles()
        assert roles[ROLE_BLUEPRINT] == "BFEditorExtensions"
        assert roles[ROLE_WIDGET] == "BFWidgetExtensions"

    def test_role_can_be_pointed_at_another_class(self, monkeypatch):
        monkeypatch.setenv("UE_EDITOR_EXTENSIONS", "blueprint=AcmeEditorExtensions")
        roles = extensions.configured_roles()
        assert roles[ROLE_BLUEPRINT] == "AcmeEditorExtensions"
        # An unmentioned role keeps its default.
        assert roles[ROLE_WIDGET] == "BFWidgetExtensions"

    def test_both_roles_overridden(self, monkeypatch):
        monkeypatch.setenv("UE_EDITOR_EXTENSIONS", "blueprint=A,widget=B")
        roles = extensions.configured_roles()
        assert roles == {ROLE_BLUEPRINT: "A", ROLE_WIDGET: "B"}

    def test_malformed_entry_is_ignored(self, monkeypatch):
        # No '=', empty class, and an unknown role: none may break the others.
        monkeypatch.setenv(
            "UE_EDITOR_EXTENSIONS", "garbage,blueprint=Good,widget=,bogusrole=X, ,"
        )
        roles = extensions.configured_roles()
        assert roles[ROLE_BLUEPRINT] == "Good"
        assert roles[ROLE_WIDGET] == "BFWidgetExtensions"
        assert "bogusrole" not in roles

    def test_class_for_role(self, monkeypatch):
        monkeypatch.setenv("UE_EDITOR_EXTENSIONS", "widget=W")
        assert extensions.class_for_role(ROLE_WIDGET) == "W"


# ---------------------------------------------------------------------------
# Probe
# ---------------------------------------------------------------------------

class TestProbe:
    def test_role_available_when_class_present(self):
        conn = _make_conn(["BFEditorExtensions"])
        assert extensions.available_roles(conn) == frozenset({ROLE_BLUEPRINT})

    def test_both_roles_available(self):
        conn = _make_conn(["BFEditorExtensions", "BFWidgetExtensions"])
        assert extensions.available_roles(conn) == frozenset({ROLE_BLUEPRINT, ROLE_WIDGET})

    def test_no_roles_on_stock_editor(self):
        conn = _make_conn([])
        assert extensions.available_roles(conn) == frozenset()

    def test_probe_uses_configured_class_name(self, monkeypatch):
        monkeypatch.setenv("UE_EDITOR_EXTENSIONS", "blueprint=AcmeEditorExtensions")
        conn = _make_conn(["AcmeEditorExtensions"])
        assert ROLE_BLUEPRINT in extensions.available_roles(conn)
        # The default name must not be probed for once overridden.
        code = conn.execute.call_args[0][0]
        assert "AcmeEditorExtensions" in code
        assert "BFEditorExtensions" not in code

    def test_probe_failure_is_not_fatal(self):
        conn = _make_conn(None, raises=RuntimeError("socket is dead"))
        assert extensions.available_roles(conn) == frozenset()

    def test_execute_not_ok_yields_nothing(self):
        conn = _make_conn([], ok=False)
        assert extensions.available_roles(conn) == frozenset()

    def test_malformed_stdout_yields_nothing(self):
        conn = _make_conn(None, stdout="not json at all")
        assert extensions.available_roles(conn) == frozenset()

    def test_unexpected_payload_shape_yields_nothing(self):
        conn = _make_conn(None, stdout=json.dumps({"available": "not-a-list"}))
        assert extensions.available_roles(conn) == frozenset()

    def test_never_connected_is_not_probed(self):
        conn = _make_conn(["BFEditorExtensions"], epoch=0)
        assert extensions.available_roles(conn) == frozenset()
        conn.execute.assert_not_called()


class TestProbeCaching:
    def test_result_is_cached_within_an_epoch(self):
        conn = _make_conn(["BFEditorExtensions"])
        extensions.available_roles(conn)
        extensions.available_roles(conn)
        extensions.available_roles(conn)
        assert conn.execute.call_count == 1

    def test_reconnect_reprobes_and_replaces_result(self):
        # First editor has the extension...
        conn = _make_conn(["BFEditorExtensions"], epoch=1)
        assert extensions.available_roles(conn) == frozenset({ROLE_BLUEPRINT})

        # ...then a reconnect lands on a stock editor. The stale "available"
        # result must not survive.
        conn.epoch = 2
        conn.execute.return_value = {
            "ok": True, "stdout": json.dumps({"available": []}), "result": None, "error": None,
        }
        assert extensions.available_roles(conn) == frozenset()
        assert conn.execute.call_count == 2
