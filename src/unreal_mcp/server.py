"""MCP server entrypoint for unreal-mcp."""

from __future__ import annotations

import json
import logging
from typing import Any

from mcp.server import Server
from mcp.server.stdio import stdio_server
from mcp.types import AnyUrl, ImageContent, Resource, TextContent, Tool

from . import extensions
from .connection import ConnectionState, get_connection
from .heartbeat import HeartbeatClient, run_heartbeat_loop
from .provisioning import provision_ue_status_module
from .reconnect import run_reconnect_loop
from .resources import content as content_resource
from .resources import level as level_resource
from .resources import world as world_resource
from .tools import actors, assets, blueprints, editor, python_exec, umg, verification

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = Server("unreal-mcp")


# ---------------------------------------------------------------------------
# Tool registry
# ---------------------------------------------------------------------------

ALL_TOOLS: list[Tool] = [
    # remote-connection
    Tool(
        name="ping",
        description="Check connection status and return UE5 version string.",
        inputSchema={"type": "object", "properties": {}, "required": []},
    ),
    # actor management
    Tool(
        name="list_actors",
        description="List all actors in the current level with label, class, and transform.",
        inputSchema={"type": "object", "properties": {}, "required": []},
    ),
    Tool(
        name="get_actor_properties",
        description="Return editable properties of a named actor as nested JSON.",
        inputSchema={
            "type": "object",
            "properties": {"label": {"type": "string", "description": "Actor label in the level"}},
            "required": ["label"],
        },
    ),
    Tool(
        name="place_actor",
        description="Spawn an actor by class path at a given transform.",
        inputSchema={
            "type": "object",
            "properties": {
                "class_path": {
                    "type": "string",
                    "description": "UE class path, e.g. /Script/Engine.PointLight",
                },
                "location": {
                    "type": "array",
                    "items": {"type": "number"},
                    "minItems": 3,
                    "maxItems": 3,
                    "description": "[X, Y, Z]",
                },
                "rotation": {
                    "type": "array",
                    "items": {"type": "number"},
                    "minItems": 3,
                    "maxItems": 3,
                    "description": "[Pitch, Yaw, Roll]",
                },
                "scale": {
                    "type": "array",
                    "items": {"type": "number"},
                    "minItems": 3,
                    "maxItems": 3,
                    "description": "[X, Y, Z]",
                },
            },
            "required": ["class_path"],
        },
    ),
    Tool(
        name="delete_actor",
        description="Remove an actor from the current level by its label.",
        inputSchema={
            "type": "object",
            "properties": {"label": {"type": "string"}},
            "required": ["label"],
        },
    ),
    Tool(
        name="set_actor_transform",
        description=(
            "Update world-space location, rotation, and/or scale of a named actor. "
            "Omit any component to leave it unchanged."
        ),
        inputSchema={
            "type": "object",
            "properties": {
                "label": {"type": "string"},
                "location": {
                    "type": "array",
                    "items": {"type": "number"},
                    "minItems": 3,
                    "maxItems": 3,
                },
                "rotation": {
                    "type": "array",
                    "items": {"type": "number"},
                    "minItems": 3,
                    "maxItems": 3,
                },
                "scale": {
                    "type": "array",
                    "items": {"type": "number"},
                    "minItems": 3,
                    "maxItems": 3,
                },
            },
            "required": ["label"],
        },
    ),
    Tool(
        name="set_actor_property",
        description="Set a named property on an actor or its component.",
        inputSchema={
            "type": "object",
            "properties": {
                "label": {"type": "string"},
                "property_path": {
                    "type": "string",
                    "description": "Dot-separated path, e.g. 'LightComponent.Intensity'",
                },
                "value": {"description": "New value (any JSON-serialisable type)"},
            },
            "required": ["label", "property_path", "value"],
        },
    ),
    # asset management
    Tool(
        name="list_assets",
        description="List assets under a content browser path.",
        inputSchema={
            "type": "object",
            "properties": {
                "path": {"type": "string", "description": "Content path, e.g. /Game/Meshes"},
                "recursive": {"type": "boolean", "default": False},
                "class_filter": {
                    "type": "string",
                    "description": "Optional asset class to filter by",
                },
            },
            "required": ["path"],
        },
    ),
    Tool(
        name="find_asset",
        description="Search for assets by name substring or glob pattern.",
        inputSchema={
            "type": "object",
            "properties": {"pattern": {"type": "string"}},
            "required": ["pattern"],
        },
    ),
    Tool(
        name="import_asset",
        description="Import a file from disk into the content browser.",
        inputSchema={
            "type": "object",
            "properties": {
                "source_path": {"type": "string", "description": "Absolute disk path to the file"},
                "destination_path": {
                    "type": "string",
                    "description": "Content browser destination, e.g. /Game/Imported",
                },
            },
            "required": ["source_path", "destination_path"],
        },
    ),
    Tool(
        name="save_asset",
        description="Save a single asset by content path.",
        inputSchema={
            "type": "object",
            "properties": {"asset_path": {"type": "string"}},
            "required": ["asset_path"],
        },
    ),
    Tool(
        name="save_all_assets",
        description="Save all dirty assets in the project.",
        inputSchema={"type": "object", "properties": {}, "required": []},
    ),
    Tool(
        name="duplicate_asset",
        description="Duplicate an asset to a new content path.",
        inputSchema={
            "type": "object",
            "properties": {
                "source_path": {"type": "string"},
                "destination_path": {"type": "string"},
            },
            "required": ["source_path", "destination_path"],
        },
    ),
    Tool(
        name="delete_asset",
        description="Delete an asset after checking for references.",
        inputSchema={
            "type": "object",
            "properties": {"asset_path": {"type": "string"}},
            "required": ["asset_path"],
        },
    ),
    # blueprint management
    Tool(
        name="create_blueprint",
        description="Create a new Blueprint asset with a given parent class.",
        inputSchema={
            "type": "object",
            "properties": {
                "asset_path": {
                    "type": "string",
                    "description": "Content path for the new Blueprint",
                },
                "parent_class": {
                    "type": "string",
                    "description": "Parent class name, e.g. Actor, Pawn, Character",
                },
            },
            "required": ["asset_path", "parent_class"],
        },
    ),
    Tool(
        name="list_blueprints",
        description="List Blueprint assets under a content path.",
        inputSchema={
            "type": "object",
            "properties": {
                "path": {"type": "string"},
                "recursive": {"type": "boolean", "default": True},
            },
            "required": ["path"],
        },
    ),
    Tool(
        name="compile_blueprint",
        description="Compile a Blueprint and return errors/warnings.",
        inputSchema={
            "type": "object",
            "properties": {"asset_path": {"type": "string"}},
            "required": ["asset_path"],
        },
    ),
    Tool(
        name="add_variable",
        description="Add a variable to a Blueprint.",
        inputSchema={
            "type": "object",
            "properties": {
                "asset_path": {"type": "string"},
                "name": {"type": "string"},
                "type": {"type": "string", "description": "e.g. Float, Boolean, Vector, Object"},
                "default_value": {"description": "Optional default value"},
            },
            "required": ["asset_path", "name", "type"],
        },
    ),
    Tool(
        name="add_function",
        description="Add an empty function graph to a Blueprint.",
        inputSchema={
            "type": "object",
            "properties": {
                "asset_path": {"type": "string"},
                "name": {"type": "string"},
            },
            "required": ["asset_path", "name"],
        },
    ),
    Tool(
        name="get_blueprint_info",
        description="Return variables, functions, and component hierarchy of a Blueprint.",
        inputSchema={
            "type": "object",
            "properties": {"asset_path": {"type": "string"}},
            "required": ["asset_path"],
        },
    ),
    Tool(
        name="call_function",
        description="Invoke a Blueprint function on a level actor or Blueprint CDO.",
        inputSchema={
            "type": "object",
            "properties": {
                "target": {
                    "type": "string",
                    "description": "Actor label or content path to Blueprint CDO",
                },
                "function_name": {"type": "string"},
                "args": {
                    "type": "object",
                    "description": "Optional keyword arguments",
                    "default": {},
                },
            },
            "required": ["target", "function_name"],
        },
    ),
    Tool(
        name="add_event_dispatcher",
        description="Add a multicast delegate (Event Dispatcher) to a Blueprint.",
        inputSchema={
            "type": "object",
            "properties": {
                "asset_path": {"type": "string"},
                "name": {
                    "type": "string",
                    "description": "Name of the dispatcher, e.g. OnBaseDestroyed",
                },
            },
            "required": ["asset_path", "name"],
        },
    ),
    # Extension-backed: UE 5.7 does not expose SimpleConstructionScript to
    # Python, so this is only offered when an editor extension provides it.
    Tool(
        name="add_component",
        description=(
            "Add a component (e.g. SphereComponent) to a Blueprint's component hierarchy. "
            "Requires an editor extension module."
        ),
        inputSchema={
            "type": "object",
            "properties": {
                "asset_path": {"type": "string"},
                "component_class": {
                    "type": "string",
                    "description": "e.g. SphereComponent, StaticMeshComponent",
                },
                "variable_name": {"type": "string"},
            },
            "required": ["asset_path", "component_class", "variable_name"],
        },
    ),
    Tool(
        name="set_variable_default",
        description=(
            "Set the default value of an existing Blueprint variable. Uses an editor "
            "extension when available; otherwise falls back to the Class Default Object, "
            "which works for variables inherited from a C++ parent class but not for "
            "Blueprint-defined ones."
        ),
        inputSchema={
            "type": "object",
            "properties": {
                "asset_path": {"type": "string"},
                "name": {"type": "string"},
                "value": {"description": "New default value"},
                "value_type": {
                    "type": "string",
                    "default": "float",
                    "description": "float, int, or bool (used by the extension path)",
                },
            },
            "required": ["asset_path", "name", "value"],
        },
    ),
    Tool(
        name="create_widget_layout",
        description=(
            "Build a UMG widget hierarchy from a JSON layout descriptor. "
            "Requires an editor extension module."
        ),
        inputSchema={
            "type": "object",
            "properties": {
                "asset_path": {"type": "string"},
                "layout": {
                    "type": "object",
                    "description": (
                        'Layout tree, e.g. {"type":"VerticalBox","name":"Root",'
                        '"children":[{"type":"TextBlock","name":"Title","text":"Hello"}]}'
                    ),
                },
            },
            "required": ["asset_path", "layout"],
        },
    ),
    Tool(
        name="add_property_binding",
        description=(
            "Bind a UMG widget property to a Blueprint function "
            "(e.g. TextBlock.Text → GetLabelText). Requires an editor extension module."
        ),
        inputSchema={
            "type": "object",
            "properties": {
                "asset_path": {"type": "string"},
                "widget_name": {"type": "string", "description": "Name of the widget in the tree"},
                "property_name": {"type": "string", "description": "e.g. Text, ColorAndOpacity"},
                "function_name": {"type": "string", "description": "Function graph to bind to"},
            },
            "required": ["asset_path", "widget_name", "property_name", "function_name"],
        },
    ),
    # UMG / Widget Blueprints
    Tool(
        name="create_widget_blueprint",
        description="Create a new Widget Blueprint asset (UserWidget subclass).",
        inputSchema={
            "type": "object",
            "properties": {
                "asset_path": {
                    "type": "string",
                    "description": "Full content path, e.g. /Game/UI/WBP_MyWidget",
                },
                "parent_class": {"type": "string", "default": "UserWidget"},
            },
            "required": ["asset_path"],
        },
    ),
    Tool(
        name="scaffold_widget",
        description="Create a Widget Blueprint and add variables and function stubs in one call.",
        inputSchema={
            "type": "object",
            "properties": {
                "asset_path": {"type": "string"},
                "variables": {
                    "type": "array",
                    "items": {
                        "type": "object",
                        "properties": {
                            "name": {"type": "string"},
                            "type": {
                                "type": "string",
                                "description": "e.g. int, float, bool, name, array:name",
                            },
                        },
                        "required": ["name", "type"],
                    },
                    "description": "Variables to add",
                },
                "functions": {
                    "type": "array",
                    "items": {"type": "string"},
                    "description": "Function stub names to add",
                },
            },
            "required": ["asset_path"],
        },
    ),
    # editor control
    Tool(
        name="play_in_editor",
        description="Start a PIE session in the currently open level.",
        inputSchema={"type": "object", "properties": {}, "required": []},
    ),
    Tool(
        name="stop_play",
        description="Stop the current PIE session.",
        inputSchema={"type": "object", "properties": {}, "required": []},
    ),
    Tool(
        name="open_level",
        description="Open a level by content browser path.",
        inputSchema={
            "type": "object",
            "properties": {"level_path": {"type": "string"}},
            "required": ["level_path"],
        },
    ),
    Tool(
        name="save_level",
        description="Save the currently open level.",
        inputSchema={"type": "object", "properties": {}, "required": []},
    ),
    Tool(
        name="run_console_command",
        description="Execute an editor console command and return output.",
        inputSchema={
            "type": "object",
            "properties": {"command": {"type": "string"}},
            "required": ["command"],
        },
    ),
    Tool(
        name="get_world_settings",
        description="Return World Settings properties as JSON.",
        inputSchema={"type": "object", "properties": {}, "required": []},
    ),
    Tool(
        name="set_world_settings",
        description="Set named properties on World Settings.",
        inputSchema={
            "type": "object",
            "properties": {
                "settings": {"type": "object", "description": "Dict of property name → value"},
            },
            "required": ["settings"],
        },
    ),
    # python execution
    Tool(
        name="execute_python",
        description=(
            "Execute arbitrary Python code in the UE5 editor context. "
            "Full trust — no restrictions applied."
        ),
        inputSchema={
            "type": "object",
            "properties": {"code": {"type": "string"}},
            "required": ["code"],
        },
    ),
    # runtime verification (visual + live state)
    Tool(
        name="take_screenshot",
        description=(
            "Capture the active viewport to a PNG and return it as an image. "
            "If a PIE session is running, captures the in-game view (HUD included); "
            "otherwise the editor viewport. Use to verify UI/visual state."
        ),
        inputSchema={
            "type": "object",
            "properties": {
                "width": {"type": "integer", "default": 1280},
                "height": {"type": "integer", "default": 720},
                "label": {
                    "type": "string",
                    "description": "Optional filename label for the saved PNG",
                },
            },
            "required": [],
        },
    ),
    Tool(
        name="inspect_live_widgets",
        description=(
            "Inspect live widget instances in the running PIE viewport, filtered by class "
            "(e.g. 'TextBlock', 'Image'). Returns each instance's runtime text, color/opacity "
            "tint, and visibility — including binding-driven values. Use to verify "
            "castable/non-castable tint and live bound readouts. Requires a running PIE session."
        ),
        inputSchema={
            "type": "object",
            "properties": {
                "widget_class": {
                    "type": "string",
                    "default": "TextBlock",
                    "description": "UMG class name, e.g. TextBlock or Image",
                },
            },
            "required": [],
        },
    ),
    Tool(
        name="list_viewport_widgets",
        description=(
            "List top-level UserWidgets currently in the PIE viewport (class, in_viewport, "
            "visibility). Use to confirm a HUD appears on the active phase and leaves no "
            "stale widgets at round end. Requires a running PIE session."
        ),
        inputSchema={"type": "object", "properties": {}, "required": []},
    ),
    Tool(
        name="set_pie_property",
        description=(
            "Set a property on a live PIE object to stage a scenario (e.g. force a player's "
            "power above/below a card cost). target: 'player0'/'player1', 'gamemode', "
            "'gamestate', or an actor label. property_path is dot-separated."
        ),
        inputSchema={
            "type": "object",
            "properties": {
                "target": {"type": "string"},
                "property_path": {"type": "string"},
                "value": {"description": "New value (any JSON-serialisable type)"},
            },
            "required": ["target", "property_path", "value"],
        },
    ),
    Tool(
        name="call_pie_function",
        description=(
            "Invoke a BlueprintCallable function on a live PIE object to drive gameplay "
            "(advance round phase, cast a card, redraw, etc.). target: 'player0'/'player1', "
            "'gamemode', 'gamestate', or an actor label."
        ),
        inputSchema={
            "type": "object",
            "properties": {
                "target": {"type": "string"},
                "function_name": {"type": "string"},
                "args": {
                    "type": "object",
                    "description": "Optional keyword arguments",
                    "default": {},
                },
            },
            "required": ["target", "function_name"],
        },
    ),
]

_TOOL_MAP = {t.name: t for t in ALL_TOOLS}

# Tools that cannot run against a stock editor because they are implemented
# against a C++ editor-extension class. Each declares the extension ROLE it
# needs; the class backing that role is configuration (see extensions.py). Tools
# absent from this map have no extension dependency and are always advertised.
_TOOL_ROLE: dict[str, str] = {
    "add_component": extensions.ROLE_BLUEPRINT,
    "create_widget_layout": extensions.ROLE_WIDGET,
    "add_property_binding": extensions.ROLE_WIDGET,
}


def _tool_is_available(name: str, available: frozenset[str]) -> bool:
    role = _TOOL_ROLE.get(name)
    return role is None or role in available


@app.list_tools()
async def list_tools() -> list[Tool]:
    available = extensions.available_roles(get_connection())
    return [t for t in ALL_TOOLS if _tool_is_available(t.name, available)]


@app.call_tool()
async def call_tool(name: str, arguments: dict[str, Any]) -> list[TextContent | ImageContent]:
    try:
        result = _dispatch(name, arguments)
    except Exception as exc:
        result = {"ok": False, "error": str(exc)}
    # A tool may attach a binary image under "_image"; emit it as ImageContent and
    # keep the rest of the payload as a text summary alongside it.
    image = result.pop("_image", None) if isinstance(result, dict) else None
    content: list[TextContent | ImageContent] = [TextContent(type="text", text=json.dumps(result))]
    if image:
        content.append(ImageContent(type="image", data=image["data"], mimeType=image["mimeType"]))
    return content


def _dispatch(name: str, args: dict[str, Any]) -> dict[str, Any]:
    conn = get_connection()

    # A client may call a tool that list_tools did not advertise. Say which
    # class is missing and what it backs, rather than failing somewhere deeper
    # with a less obvious message.
    role = _TOOL_ROLE.get(name)
    if role is not None and role not in extensions.available_roles(conn):
        class_name = extensions.class_for_role(role)
        return {
            "ok": False,
            "error": (
                f"'{name}' needs the '{role}' editor extension, expected as class "
                f"'{class_name}', which the connected editor does not expose. Build "
                f"the C++ editor module that provides it, or point the role at "
                f"another class via UE_EDITOR_EXTENSIONS."
            ),
            "missing_role": role,
            "missing_class": class_name,
        }

    match name:
        case "ping":
            return conn.ping()
        case "list_actors":
            return actors.list_actors(conn)
        case "get_actor_properties":
            return actors.get_actor_properties(conn, args["label"])
        case "place_actor":
            return actors.place_actor(
                conn,
                args["class_path"],
                args.get("location"),
                args.get("rotation"),
                args.get("scale"),
            )
        case "delete_actor":
            return actors.delete_actor(conn, args["label"])
        case "set_actor_transform":
            return actors.set_actor_transform(
                conn,
                args["label"],
                args.get("location"),
                args.get("rotation"),
                args.get("scale"),
            )
        case "set_actor_property":
            return actors.set_actor_property(
                conn, args["label"], args["property_path"], args["value"]
            )
        case "list_assets":
            return assets.list_assets(
                conn, args["path"], args.get("recursive", False), args.get("class_filter")
            )
        case "find_asset":
            return assets.find_asset(conn, args["pattern"])
        case "import_asset":
            return assets.import_asset(conn, args["source_path"], args["destination_path"])
        case "save_asset":
            return assets.save_asset(conn, args["asset_path"])
        case "save_all_assets":
            return assets.save_all_assets(conn)
        case "duplicate_asset":
            return assets.duplicate_asset(conn, args["source_path"], args["destination_path"])
        case "delete_asset":
            return assets.delete_asset(conn, args["asset_path"])
        case "create_blueprint":
            return blueprints.create_blueprint(conn, args["asset_path"], args["parent_class"])
        case "list_blueprints":
            return blueprints.list_blueprints(conn, args["path"], args.get("recursive", True))
        case "compile_blueprint":
            return blueprints.compile_blueprint(conn, args["asset_path"])
        case "add_variable":
            return blueprints.add_variable(
                conn, args["asset_path"], args["name"], args["type"], args.get("default_value")
            )
        case "add_function":
            return blueprints.add_function(conn, args["asset_path"], args["name"])
        case "get_blueprint_info":
            return blueprints.get_blueprint_info(conn, args["asset_path"])
        case "call_function":
            return blueprints.call_function(
                conn, args["target"], args["function_name"], args.get("args", {})
            )
        case "add_event_dispatcher":
            return blueprints.add_event_dispatcher(conn, args["asset_path"], args["name"])
        case "add_component":
            return blueprints.add_component_cpp(
                conn,
                args["asset_path"],
                args["component_class"],
                args["variable_name"],
                extensions.class_for_role(extensions.ROLE_BLUEPRINT),
            )
        case "set_variable_default":
            # Prefer the extension, which can also reach Blueprint-defined
            # variables; otherwise fall back to the CDO path, which handles
            # variables inherited from a C++ parent class.
            if extensions.ROLE_BLUEPRINT in extensions.available_roles(conn):
                return blueprints.set_variable_default_cpp(
                    conn,
                    args["asset_path"],
                    args["name"],
                    args["value"],
                    args.get("value_type", "float"),
                    extensions.class_for_role(extensions.ROLE_BLUEPRINT),
                )
            return blueprints.set_variable_default(
                conn, args["asset_path"], args["name"], args["value"]
            )
        case "create_widget_blueprint":
            return umg.create_widget_blueprint(
                conn, args["asset_path"], args.get("parent_class", "UserWidget")
            )
        case "scaffold_widget":
            return umg.scaffold_widget(
                conn, args["asset_path"], args.get("variables"), args.get("functions")
            )
        case "create_widget_layout":
            return umg.create_widget_layout(
                conn,
                args["asset_path"],
                args["layout"],
                extensions.class_for_role(extensions.ROLE_WIDGET),
            )
        case "add_property_binding":
            return umg.add_property_binding(
                conn,
                args["asset_path"],
                args["widget_name"],
                args["property_name"],
                args["function_name"],
                extensions.class_for_role(extensions.ROLE_WIDGET),
            )
        case "play_in_editor":
            return editor.play_in_editor(conn)
        case "stop_play":
            return editor.stop_play(conn)
        case "open_level":
            return editor.open_level(conn, args["level_path"])
        case "save_level":
            return editor.save_level(conn)
        case "run_console_command":
            return editor.run_console_command(conn, args["command"])
        case "get_world_settings":
            return editor.get_world_settings(conn)
        case "set_world_settings":
            return editor.set_world_settings(conn, args["settings"])
        case "execute_python":
            return python_exec.execute_python(conn, args["code"])
        case "take_screenshot":
            return verification.take_screenshot(
                conn, args.get("width", 1280), args.get("height", 720), args.get("label")
            )
        case "inspect_live_widgets":
            return verification.inspect_live_widgets(conn, args.get("widget_class", "TextBlock"))
        case "list_viewport_widgets":
            return verification.list_viewport_widgets(conn)
        case "set_pie_property":
            return verification.set_pie_property(
                conn, args["target"], args["property_path"], args["value"]
            )
        case "call_pie_function":
            return verification.call_pie_function(
                conn, args["target"], args["function_name"], args.get("args", {})
            )
        case _:
            return {"ok": False, "error": f"Unknown tool: {name}"}


# ---------------------------------------------------------------------------
# Resource registry
# ---------------------------------------------------------------------------

ALL_RESOURCES = [
    Resource(
        uri=AnyUrl("unreal://level/hierarchy"),
        name="Level Hierarchy",
        description="Live actor tree of the current level",
        mimeType="application/json",
    ),
    Resource(
        uri=AnyUrl("unreal://content/tree"),
        name="Content Tree",
        description="Live content browser folder and asset tree",
        mimeType="application/json",
    ),
    Resource(
        uri=AnyUrl("unreal://world/settings"),
        name="World Settings",
        description="Live World Settings properties",
        mimeType="application/json",
    ),
]


@app.list_resources()
async def list_resources() -> list[Resource]:
    return ALL_RESOURCES


@app.read_resource()
async def read_resource(uri: Any) -> str:
    conn = get_connection()
    uri_str = str(uri)
    match uri_str:
        case "unreal://level/hierarchy":
            result = level_resource.get_hierarchy(conn)
        case "unreal://content/tree":
            result = content_resource.get_tree(conn)
        case "unreal://world/settings":
            result = world_resource.get_settings(conn)
        case _:
            result = {"error": f"Unknown resource: {uri_str}"}
    return json.dumps(result)


# ---------------------------------------------------------------------------
# CLI entrypoint
# ---------------------------------------------------------------------------

def main() -> None:
    import asyncio
    asyncio.run(_run())


async def _run() -> None:
    import asyncio
    import sys
    _server_command = [sys.executable, "-m", "unreal_mcp.server"]

    conn = get_connection()
    # Don't block the event loop — let the background reconnect task own the first connect.
    conn.state = ConnectionState.CONNECTING

    def _provision(c: object) -> None:
        provision_ue_status_module(c, server_command=_server_command)  # type: ignore[arg-type]

    # Background reconnect task owns all RE reconnection with exponential backoff.
    reconnect_task = asyncio.create_task(run_reconnect_loop(conn, on_connect=_provision))

    # Heartbeat channel to the C++ status plugin (non-fatal if it can't connect).
    heartbeat_client = HeartbeatClient()
    await heartbeat_client.connect()
    heartbeat_task = asyncio.create_task(run_heartbeat_loop(heartbeat_client))

    try:
        async with stdio_server() as streams:
            await app.run(streams[0], streams[1], app.create_initialization_options())
    finally:
        # Stop heartbeat first so it can emit a clean `stopped` event, then the
        # reconnect task, then close the RE socket.
        for task in (heartbeat_task, reconnect_task):
            task.cancel()
            try:
                await task
            except asyncio.CancelledError:
                pass
        await heartbeat_client.close()
        conn.disconnect()


if __name__ == "__main__":
    main()
