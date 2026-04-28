from __future__ import annotations

from typing import Any

from flask_mcp_lens.tools import envelope, get_manager


def list_extensions() -> dict[str, Any]:
    index = get_manager().get()
    ext_list = [
        {
            "name": e.name,
            "package": e.package,
            "declared_in": list(e.declared_in),
            "imported_in": [
                {"file": loc.file, "line": loc.line} for loc in e.imported_in
            ],
            "initialized_at": (
                {"file": e.initialized_at.file, "line": e.initialized_at.line}
                if e.initialized_at else None
            ),
            "confidence": e.confidence,
            "config_available": bool(e.config),
        }
        for e in index.extensions
    ]
    # unsupported は index に保存されていないため空リスト（Phase 3 で対応）
    return envelope(
        "list_extensions",
        {"extensions": ext_list, "unsupported_detected": []},
        warnings=list(index.warnings),
    )
