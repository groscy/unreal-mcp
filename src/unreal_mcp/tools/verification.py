"""Runtime verification tools.

These tools support visual and live-state verification of gameplay/UI during a
PIE (Play-In-Editor) session — capturing screenshots, reading a Widget
Blueprint's rendered tree, enumerating viewport widgets, and driving or mutating
live PIE objects to set up deterministic test scenarios.

The MCP server runs on the same machine as the UE editor, so ``take_screenshot``
reads the rendered PNG straight off disk and returns it as an image payload.
"""

from __future__ import annotations

import base64
import glob
import json
import os
import time
from typing import Any

from ..connection import UEConnection
from ._util import pyval


# Shared snippet: resolve the live PIE/game world and its player controller.
# Passing ``None`` as a world context resolves against the *editor* world (which
# has no player controller during PIE), so every PIE tool must use this instead.
_GAME_CTX = """
def _game_world():
    try:
        ues = unreal.get_editor_subsystem(unreal.UnrealEditorSubsystem)
        return ues.get_game_world()
    except Exception:
        return None

def _pie_pc(idx=0):
    gw = _game_world()
    if gw is None:
        return None
    return unreal.GameplayStatics.get_player_controller(gw, idx)
"""


def _run_and_parse(conn: UEConnection, code: str) -> dict[str, Any]:
    result = conn.execute(code)
    if not result["ok"]:
        return result
    stdout = (result.get("stdout") or "").strip()
    if stdout:
        # Snippets may print log lines before the final JSON; take the last JSON line.
        for line in reversed(stdout.splitlines()):
            line = line.strip()
            if line.startswith("{") and line.endswith("}"):
                try:
                    return json.loads(line)
                except json.JSONDecodeError:
                    continue
    if isinstance(result.get("result"), dict):
        return result["result"]
    return result


# ---------------------------------------------------------------------------
# Screenshot capture
# ---------------------------------------------------------------------------

def take_screenshot(
    conn: UEConnection,
    width: int = 1280,
    height: int = 720,
    label: str | None = None,
    timeout: float = 20.0,
) -> dict[str, Any]:
    """Capture the active viewport (PIE game view if playing, else editor) to a PNG.

    Issues a ``HighResShot`` request, polls the screenshot directory on disk for
    the resulting file, then returns it as an image payload (base64 PNG) plus the
    absolute path. During PIE the command is routed through the local player
    controller so the captured frame includes the in-game HUD.
    """
    token = "mcp_" + (label or "shot")
    # Strip characters that wouldn't survive as a filename.
    token = "".join(c for c in token if c.isalnum() or c in ("_", "-"))

    request_code = f"""
import unreal, json
{_GAME_CTX}
w, h = {int(width)}, {int(height)}
token = {json.dumps(token)}
cmd = "HighResShot %dx%d filename=%s" % (w, h, token)
# A player controller only exists during PIE; passing it as the world context
# routes the command to the game viewport so the shot includes the in-game HUD.
pc = _pie_pc(0)
is_pie = pc is not None
world_ctx = pc if pc else unreal.EditorLevelLibrary.get_editor_world()
unreal.SystemLibrary.execute_console_command(world_ctx, cmd)
sdir = unreal.Paths.convert_relative_path_to_full(unreal.Paths.screen_shot_dir())
print(json.dumps({{"ok": True, "dir": sdir, "token": token, "is_pie": is_pie}}))
"""
    req = _run_and_parse(conn, request_code)
    if not req.get("ok"):
        return req

    sdir = req["dir"]
    # HighResShot writes <token>.png (or <token>00000.png); scan for newest match.
    pattern = os.path.join(sdir, "**", f"{token}*.png")
    deadline = time.time() + timeout
    path: str | None = None
    while time.time() < deadline:
        matches = glob.glob(pattern, recursive=True)
        if matches:
            newest = max(matches, key=os.path.getmtime)
            if os.path.getsize(newest) > 0:
                path = newest
                break
        time.sleep(0.4)

    if path is None:
        return {
            "ok": False,
            "error": f"Screenshot file not found within {timeout:.0f}s under {sdir} (looked for '{token}*.png')",
            "dir": sdir,
            "is_pie": req.get("is_pie"),
        }

    # Let the file finish flushing before reading.
    time.sleep(0.2)
    with open(path, "rb") as f:
        data = f.read()

    return {
        "ok": True,
        "path": path,
        "is_pie": req.get("is_pie"),
        "bytes": len(data),
        "_image": {"data": base64.b64encode(data).decode("ascii"), "mimeType": "image/png"},
    }


# ---------------------------------------------------------------------------
# Widget Blueprint introspection
# ---------------------------------------------------------------------------

def inspect_live_widgets(conn: UEConnection, widget_class: str = "TextBlock") -> dict[str, Any]:
    """Inspect live widget instances in the running PIE viewport, by class.

    Returns each instance's name, rendered text (for TextBlocks), color/opacity
    tint, and visibility — the *runtime* values, including binding-driven ones.
    This is what verifies castable/non-castable tint (``Image``) and live bound
    readouts like power/deck/discard text (``TextBlock``). Requires a running PIE
    session.
    """
    code = f"""
import unreal, json
{_GAME_CTX}
class_name = {json.dumps(widget_class)}

def safe(fn):
    try:
        return fn()
    except Exception as e:
        return "err:%s" % e

cls = getattr(unreal, class_name, None)
pc = _pie_pc(0)
if pc is None:
    print(json.dumps({{"ok": False, "error": "No PIE player controller — start a PIE session first."}}))
elif cls is None:
    print(json.dumps({{"ok": False, "error": "Unknown widget class '%s'" % class_name}}))
else:
    try:
        found = unreal.WidgetLibrary.get_all_widgets_of_class(pc, cls, False)
    except Exception as e:
        found = []
    out = []
    for w in found:
        e = {{"name": w.get_name(), "class": w.get_class().get_name()}}
        try:
            e["text"] = str(w.get_editor_property("text"))
        except Exception:
            pass
        for prop in ("color_and_opacity", "brush_color"):
            try:
                c = w.get_editor_property(prop)
                e["color"] = {{"prop": prop, "rgba": [round(c.r,3), round(c.g,3), round(c.b,3), round(c.a,3)]}}
                break
            except Exception:
                continue
        e["visibility"] = safe(lambda: str(w.get_visibility()))
        out.append(e)
    print(json.dumps({{"ok": True, "widget_class": class_name, "count": len(out), "widgets": out}}))
"""
    return _run_and_parse(conn, code)


# ---------------------------------------------------------------------------
# Live viewport widgets (PIE lifecycle)
# ---------------------------------------------------------------------------

def list_viewport_widgets(conn: UEConnection) -> dict[str, Any]:
    """List top-level UserWidgets currently constructed in the PIE world.

    For each widget reports its class, whether it is added to the viewport, and
    its visibility — enough to verify a HUD appears on the active phase and is
    fully removed (no stale widgets) at round end.
    """
    code = f"""
import unreal, json
{_GAME_CTX}
pc = _pie_pc(0)
if pc is None:
    print(json.dumps({{"ok": False, "error": "No PIE player controller — is a PIE session running?"}}))
else:
    try:
        found = unreal.WidgetLibrary.get_all_widgets_of_class(pc, unreal.UserWidget, True)
    except Exception as e:
        found = []
    out = []
    for w in found:
        def safe(fn):
            try:
                return fn()
            except Exception as e:
                return "err:%s" % e
        out.append({{
            "class": w.get_class().get_name(),
            "in_viewport": safe(lambda: bool(w.is_in_viewport())),
            "visibility": safe(lambda: str(w.get_visibility())),
        }})
    print(json.dumps({{"ok": True, "count": len(out), "widgets": out}}))
"""
    return _run_and_parse(conn, code)


# ---------------------------------------------------------------------------
# Drive / mutate live PIE objects
# ---------------------------------------------------------------------------

_RESOLVE_TARGET = _GAME_CTX + """
def _resolve(target):
    gw = _game_world()
    if gw is None:
        return None
    # player0/player1 -> PlayerController by index
    if isinstance(target, str) and target.lower().startswith("player"):
        try:
            idx = int(target[6:] or "0")
        except ValueError:
            idx = 0
        return unreal.GameplayStatics.get_player_controller(gw, idx)
    if target == "gamemode":
        return unreal.GameplayStatics.get_game_mode(gw)
    if target == "gamestate":
        return unreal.GameplayStatics.get_game_state(gw)
    # otherwise treat as a level actor label (resolve against the PIE world)
    for a in unreal.GameplayStatics.get_all_actors_of_class(gw, unreal.Actor):
        if a.get_actor_label() == target:
            return a
    return None
"""


def set_pie_property(
    conn: UEConnection,
    target: str,
    property_path: str,
    value: Any,
) -> dict[str, Any]:
    """Set a property on a live PIE object to stage a scenario.

    ``target`` is ``player0``/``player1``, ``gamemode``, ``gamestate``, or an
    actor label. ``property_path`` is dot-separated (e.g. ``power_pool`` or
    ``hand_manager.deck_cards``). Use this to force affordability extremes, e.g.
    drive a player's power above/below a card cost.
    """
    code = f"""
import unreal, json
{_RESOLVE_TARGET}
target = {json.dumps(target)}
property_path = {json.dumps(property_path)}
value = {pyval(value)}
obj = _resolve(target)
if obj is None:
    print(json.dumps({{"ok": False, "error": "Could not resolve PIE target '%s'" % target}}))
else:
    parts = property_path.split(".")
    node = obj
    err = None
    for p in parts[:-1]:
        node = node.get_editor_property(p)
    try:
        node.set_editor_property(parts[-1], value)
        readback = node.get_editor_property(parts[-1])
        print(json.dumps({{"ok": True, "target": target, "property": property_path, "value": str(readback)}}))
    except Exception as e:
        print(json.dumps({{"ok": False, "error": "Set '%s' on '%s': %s" % (property_path, target, e)}}))
"""
    return _run_and_parse(conn, code)


def call_pie_function(
    conn: UEConnection,
    target: str,
    function_name: str,
    args: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Invoke a BlueprintCallable function on a live PIE object.

    ``target`` is ``player0``/``player1``, ``gamemode``, ``gamestate``, or an
    actor label. Use this to advance the round phase, cast a card, redraw a hand,
    etc., so a verification scenario can be driven deterministically.
    """
    args = args or {}
    code = f"""
import unreal, json
{_RESOLVE_TARGET}
target = {json.dumps(target)}
function_name = {json.dumps(function_name)}
kwargs = {json.dumps(args)}
obj = _resolve(target)
if obj is None:
    print(json.dumps({{"ok": False, "error": "Could not resolve PIE target '%s'" % target}}))
else:
    try:
        ret = obj.call_method(function_name, kwargs=kwargs) if kwargs else obj.call_method(function_name)
        print(json.dumps({{"ok": True, "target": target, "function": function_name, "result": str(ret)}}))
    except Exception as e:
        print(json.dumps({{"ok": False, "error": "Call '%s' on '%s': %s" % (function_name, target, e)}}))
"""
    return _run_and_parse(conn, code)
