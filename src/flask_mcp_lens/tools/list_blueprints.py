from __future__ import annotations

from typing import Any

from flask_mcp_lens.tools import envelope, get_manager


def list_blueprints() -> dict[str, Any]:
    index = get_manager().get()
    status_map = {bs.blueprint: bs for bs in index.blueprint_status}

    result = []
    for bp in index.blueprints:
        bs = status_map.get(bp.name)
        status = bs.status if bs else "unregistered"
        route_count = sum(1 for r in index.routes if r.blueprint == bp.name)
        own_prefix = bp.url_prefix
        if bp.registrations and bp.registrations[0].url_prefix_override is not None:
            own_prefix = bp.registrations[0].url_prefix_override
        result.append({
            "name": bp.name,
            "definition": {"file": bp.file.file, "line": bp.file.line},
            "url_prefix": bp.url_prefix,
            "parent": bp.parent,
            "effective_url_prefix": own_prefix if status != "unregistered" else None,
            "status": status,
            "registrations": [
                {
                    "file": reg.location.file,
                    "line": reg.location.line,
                    "url_prefix_override": reg.url_prefix_override,
                }
                for reg in bp.registrations
            ],
            "route_count": route_count,
        })

    unregistered_count = sum(
        1 for bp in index.blueprints if not bp.registrations
    )
    return envelope(
        "list_blueprints",
        {
            "blueprints": result,
            "total": len(result),
            "unregistered_count": unregistered_count,
        },
        warnings=list(index.warnings),
    )
