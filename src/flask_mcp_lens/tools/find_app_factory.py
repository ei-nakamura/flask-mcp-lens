from __future__ import annotations

from typing import Any

from flask_mcp_lens.tools import envelope, get_manager


def find_app_factory() -> dict[str, Any]:
    index = get_manager().get()
    return envelope(
        "find_app_factory",
        {
            "candidates": [
                {
                    "kind": c.kind,
                    "name": c.name,
                    "file": c.location.file,
                    "line": c.location.line,
                    "params": list(c.params),
                    "confidence": c.confidence,
                }
                for c in index.app_factories
            ],
            "selected": index.selected_factory if index.app_factories else None,
        },
        warnings=list(index.warnings),
    )
