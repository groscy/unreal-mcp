"""Shared helpers for tool snippet generation."""

from __future__ import annotations

import json
from typing import Any


def pyval(v: Any) -> str:
    """Serialize a Python value as a valid Python literal for code injection.

    json.dumps() returns 'true'/'false'/'null' which are not valid Python.
    This function returns 'True'/'False'/'None' instead.
    """
    if v is None:
        return "None"
    if isinstance(v, bool):
        return "True" if v else "False"
    return json.dumps(v)
