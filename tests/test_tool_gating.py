"""Tests for extension-gated tool registration and dispatch — no live UE required."""

from unittest.mock import MagicMock, patch

import pytest

from unreal_mcp import extensions, server
from unreal_mcp.extensions import ROLE_BLUEPRINT, ROLE_WIDGET

GATED = ["add_component", "create_widget_layout", "add_property_binding"]


@pytest.fixture(autouse=True)
def _clear(monkeypatch):
    monkeypatch.delenv("UE_EDITOR_EXTENSIONS", raising=False)
    extensions.reset_cache()
    yield
    extensions.reset_cache()


def _with_roles(roles):
    """Patch the probe to report `roles` as available."""
    return patch.object(server.extensions, "available_roles", return_value=frozenset(roles))


async def _names(roles):
    with _with_roles(roles), patch.object(server, "get_connection", return_value=MagicMock()):
        return [t.name for t in await server.list_tools()]


# ---------------------------------------------------------------------------
# Registration gating
# ---------------------------------------------------------------------------

class TestListToolsGating:
    async def test_gated_tools_hidden_on_stock_editor(self):
        names = await _names([])
        for name in GATED:
            assert name not in names

    async def test_widget_role_reveals_widget_tools(self):
        names = await _names([ROLE_WIDGET])
        assert "create_widget_layout" in names
        assert "add_property_binding" in names
        # A different role must not leak in.
        assert "add_component" not in names

    async def test_blueprint_role_reveals_add_component(self):
        names = await _names([ROLE_BLUEPRINT])
        assert "add_component" in names
        assert "create_widget_layout" not in names

    async def test_all_roles_reveals_everything(self):
        names = await _names([ROLE_BLUEPRINT, ROLE_WIDGET])
        for name in GATED:
            assert name in names

    async def test_ungated_tools_always_advertised(self):
        bare = await _names([])
        full = await _names([ROLE_BLUEPRINT, ROLE_WIDGET])
        for name in ["ping", "list_actors", "create_blueprint", "take_screenshot",
                     "set_variable_default", "execute_python"]:
            assert name in bare, f"{name} must not depend on an extension"
            assert name in full

    async def test_removed_battleforge_tool_is_gone(self):
        # inspect_pie_state was game-domain logic, not an engine capability.
        assert "inspect_pie_state" not in await _names([ROLE_BLUEPRINT, ROLE_WIDGET])


class TestNoDuplicateToolNames:
    @pytest.mark.parametrize(
        "roles",
        [[], [ROLE_BLUEPRINT], [ROLE_WIDGET], [ROLE_BLUEPRINT, ROLE_WIDGET]],
        ids=["none", "blueprint", "widget", "both"],
    )
    async def test_names_unique_under_every_role_combination(self, roles):
        names = await _names(roles)
        dupes = {n for n in names if names.count(n) > 1}
        assert not dupes, f"duplicate tool names advertised: {dupes}"

    def test_registration_table_has_no_duplicates(self):
        names = [t.name for t in server.ALL_TOOLS]
        dupes = {n for n in names if names.count(n) > 1}
        assert not dupes, f"ALL_TOOLS registers duplicate names: {dupes}"


# ---------------------------------------------------------------------------
# Dispatch
# ---------------------------------------------------------------------------

class TestHiddenToolCalledAnyway:
    def test_returns_structured_error_naming_class_and_role(self):
        conn = MagicMock()
        with _with_roles([]), patch.object(server, "get_connection", return_value=conn):
            result = server._dispatch("add_component", {
                "asset_path": "/Game/BP/X", "component_class": "SphereComponent",
                "variable_name": "Comp",
            })
        assert result["ok"] is False
        assert result["missing_role"] == ROLE_BLUEPRINT
        assert result["missing_class"] == "BFEditorExtensions"
        assert "BFEditorExtensions" in result["error"]
        # It must not have tried to talk to the editor.
        conn.execute.assert_not_called()

    def test_error_names_the_configured_class_not_the_default(self, monkeypatch):
        monkeypatch.setenv("UE_EDITOR_EXTENSIONS", "widget=AcmeWidgets")
        with _with_roles([]), patch.object(server, "get_connection", return_value=MagicMock()):
            result = server._dispatch("create_widget_layout", {
                "asset_path": "/Game/W", "layout": {"type": "CanvasPanel"},
            })
        assert result["missing_class"] == "AcmeWidgets"
        assert result["missing_role"] == ROLE_WIDGET


class TestSetVariableDefaultResolution:
    """set_variable_default is always advertised; the implementation is chosen at call time."""

    ARGS = {"asset_path": "/Game/BP/X", "name": "Health", "value": 5.0}

    def test_uses_extension_when_blueprint_role_available(self):
        conn = MagicMock()
        with _with_roles([ROLE_BLUEPRINT]), \
             patch.object(server, "get_connection", return_value=conn), \
             patch.object(server.blueprints, "set_variable_default_cpp") as cpp, \
             patch.object(server.blueprints, "set_variable_default") as py:
            cpp.return_value = {"ok": True}
            server._dispatch("set_variable_default", dict(self.ARGS, value_type="float"))
        cpp.assert_called_once()
        py.assert_not_called()
        # The configured class name must be threaded through to the snippet.
        assert cpp.call_args[0][-1] == "BFEditorExtensions"

    def test_falls_back_to_cdo_path_without_the_role(self):
        conn = MagicMock()
        with _with_roles([]), \
             patch.object(server, "get_connection", return_value=conn), \
             patch.object(server.blueprints, "set_variable_default_cpp") as cpp, \
             patch.object(server.blueprints, "set_variable_default") as py:
            py.return_value = {"ok": True}
            server._dispatch("set_variable_default", dict(self.ARGS))
        py.assert_called_once()
        cpp.assert_not_called()

    def test_fallback_surfaces_blueprint_defined_variable_error(self):
        # The CDO path cannot reach Blueprint-defined variables on UE 5.7; the
        # tool must return that as a structured, actionable error.
        conn = MagicMock()
        conn.execute.return_value = {
            "ok": True,
            "stdout": '{"ok": false, "error": "boom", "hint": "Blueprint-defined variables '
                      'are not accessible via Python CDO in UE 5.7. Set the default in the '
                      'Blueprint Class Defaults panel instead."}',
            "result": None,
            "error": None,
        }
        with _with_roles([]), patch.object(server, "get_connection", return_value=conn):
            result = server._dispatch("set_variable_default", dict(self.ARGS))
        assert result["ok"] is False
        assert "Blueprint-defined variables" in result["hint"]

    def test_missing_asset_path_is_reported(self):
        conn = MagicMock()
        conn.execute.return_value = {
            "ok": True,
            "stdout": '{"ok": false, "error": "Not found: /Game/BP/Nope"}',
            "result": None,
            "error": None,
        }
        with _with_roles([]), patch.object(server, "get_connection", return_value=conn):
            result = server._dispatch(
                "set_variable_default", dict(self.ARGS, asset_path="/Game/BP/Nope")
            )
        assert result["ok"] is False
        assert "Not found" in result["error"]
