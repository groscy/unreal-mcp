"""Python execution tool — forwards raw code to UE5 with no restrictions."""

from __future__ import annotations

from typing import Any

from ..connection import UEConnection


def execute_python(conn: UEConnection, code: str) -> dict[str, Any]:
    """Execute arbitrary Python in the UE5 editor context.

    No filtering, validation, or sandboxing is applied.
    Returns stdout, result, and any exception traceback.
    """
    result = conn.execute(code)
    # Normalise to the execute_python-specific shape
    return {
        "ok": result["ok"],
        "stdout": result.get("stdout", ""),
        "result": result.get("result"),
        "error": result.get("error"),
    }
