from __future__ import annotations

from typing import Any

from flask_mcp_lens.index import IndexManager

_manager: IndexManager | None = None


def init(manager: IndexManager) -> None:
    global _manager
    _manager = manager


def get_manager() -> IndexManager:
    if _manager is None:
        raise RuntimeError("IndexManager not initialized. Call tools.init() first.")
    return _manager


def envelope(
    tool_name: str,
    data: dict[str, Any],
    warnings: list[str] | None = None,
) -> dict[str, Any]:
    return {
        "tool": tool_name,
        "version": "1.0",
        "analysis_mode": "static",
        "warnings": warnings or [],
        "data": data,
    }
