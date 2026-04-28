from __future__ import annotations

from typing import Any

from flask_mcp_lens.tools import envelope, get_manager

_SUPPORTED = {"flask_login", "flask_jwt_extended"}


def get_extension_config(name: str) -> dict[str, Any]:
    index = get_manager().get()
    if name not in _SUPPORTED:
        return envelope(
            "get_extension_config",
            {"error": "extension not found or not yet supported"},
            warnings=list(index.warnings),
        )

    ext = next((e for e in index.extensions if e.name == name), None)
    if ext is None:
        return envelope(
            "get_extension_config",
            {"error": f"{name} not detected in this project"},
            warnings=list(index.warnings),
        )

    return envelope(
        "get_extension_config",
        {
            "name": ext.name,
            "initialized_at": (
                {"file": ext.initialized_at.file, "line": ext.initialized_at.line}
                if ext.initialized_at else None
            ),
            "config": ext.config,
        },
        warnings=list(index.warnings),
    )
