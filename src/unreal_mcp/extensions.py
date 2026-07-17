"""Optional C++ editor-extension contract.

Some tools cannot be implemented against the stock UE Python API and are backed
instead by a C++ editor module that exposes extra classes on the ``unreal``
module. That module is not part of this repo, so those tools only work against
an editor that has it built.

Rather than advertise tools that cannot run, the server asks the *connected
editor* which extension classes it exposes and registers the dependent tools
only when they are present. Availability is a property of the editor on the
other end of the connection, not of this installation: the same install can be
pointed at an editor with the module and then at one without, so the result is
cached per connection epoch and re-derived after a reconnect.

Extensions are configured by ROLE rather than as a bare list of class names,
because a tool does not merely need some class to exist -- it calls named
methods on a specific one, and must know which class backs Blueprints versus
widgets. ``UE_EDITOR_EXTENSIONS`` maps roles to class names:

    UE_EDITOR_EXTENSIONS="blueprint=BFEditorExtensions,widget=BFWidgetExtensions"

The method set a class must expose is the real contract; the class name is
configuration. Pointing a role at another class means supplying one that
implements the same methods.
"""

from __future__ import annotations

import json
import logging
import os

from .connection import UEConnection

logger = logging.getLogger(__name__)

ROLE_BLUEPRINT = "blueprint"
ROLE_WIDGET = "widget"

DEFAULT_EXTENSION_ROLES: dict[str, str] = {
    ROLE_BLUEPRINT: "BFEditorExtensions",
    ROLE_WIDGET: "BFWidgetExtensions",
}

# (epoch, available roles) for the connection we last probed. epoch 0 means
# "never connected", which no successful probe can produce, so it is a safe
# sentinel.
_cache: tuple[int, frozenset[str]] | None = None


def configured_roles() -> dict[str, str]:
    """Role -> class name, from UE_EDITOR_EXTENSIONS.

    Malformed entries and unknown roles are ignored rather than fatal: a typo in
    an env var should not stop the server from serving every non-extension tool.
    Roles left unmentioned keep their default class name.
    """
    roles = dict(DEFAULT_EXTENSION_ROLES)
    raw = os.environ.get("UE_EDITOR_EXTENSIONS")
    if not raw:
        return roles

    for entry in raw.split(","):
        entry = entry.strip()
        if not entry:
            continue
        role, sep, class_name = entry.partition("=")
        role, class_name = role.strip(), class_name.strip()
        if not sep or not role or not class_name:
            logger.warning("Ignoring malformed UE_EDITOR_EXTENSIONS entry: %r", entry)
            continue
        if role not in DEFAULT_EXTENSION_ROLES:
            logger.warning(
                "Ignoring unknown extension role %r (known roles: %s)",
                role,
                ", ".join(sorted(DEFAULT_EXTENSION_ROLES)),
            )
            continue
        roles[role] = class_name
    return roles


def class_for_role(role: str) -> str:
    """The class name configured for ``role``."""
    return configured_roles()[role]


def _probe(conn: UEConnection, roles: dict[str, str]) -> frozenset[str]:
    """Ask the editor which configured classes it exposes. Never raises."""
    if not roles:
        return frozenset()
    names = sorted(set(roles.values()))
    code = f"""
import unreal, json
names = {json.dumps(names)}
print(json.dumps({{"available": [n for n in names if hasattr(unreal, n)]}}))
"""
    try:
        result = conn.execute(code)
    except Exception as exc:  # editor gone, socket dead, anything
        logger.debug("Extension probe failed: %s", exc)
        return frozenset()

    if not isinstance(result, dict) or not result.get("ok"):
        logger.debug("Extension probe returned no result: %r", result)
        return frozenset()

    # Snippets report through stdout, matching tools/_util conventions.
    stdout = (result.get("stdout") or "").strip()
    try:
        payload = json.loads(stdout)
    except (json.JSONDecodeError, TypeError):
        logger.debug("Extension probe stdout not JSON: %r", stdout)
        return frozenset()
    if not isinstance(payload, dict):
        return frozenset()

    available_classes = payload.get("available")
    if not isinstance(available_classes, list):
        return frozenset()
    present = {str(n) for n in available_classes if isinstance(n, str)}
    return frozenset(role for role, cls in roles.items() if cls in present)


def available_roles(conn: UEConnection) -> frozenset[str]:
    """Extension roles the connected editor can satisfy.

    Cached per connection epoch. A probe that cannot be completed -- because the
    editor is disconnected, unresponsive, or answers with nonsense -- is treated
    as "nothing available" rather than an error, so a stock editor and a broken
    one degrade the same way: the dependent tools simply are not offered.
    """
    global _cache
    epoch = conn.epoch
    if epoch == 0:
        # Never connected: nothing to probe, and nothing worth caching.
        return frozenset()
    if _cache is not None and _cache[0] == epoch:
        return _cache[1]

    available = _probe(conn, configured_roles())
    _cache = (epoch, available)
    if available:
        logger.info("Editor extension roles available: %s", ", ".join(sorted(available)))
    return available


def reset_cache() -> None:
    """Drop the cached probe result. Intended for tests."""
    global _cache
    _cache = None
