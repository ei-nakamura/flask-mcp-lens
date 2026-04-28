from __future__ import annotations

from typing import Any, Optional

from flask_mcp_lens.tools import envelope, get_manager


def list_routes(filter: Optional[dict[str, Any]] = None) -> dict[str, Any]:
    index = get_manager().get()
    routes = list(index.routes)
    total_all = len(routes)

    if filter:
        bp_filter = filter.get("blueprint")
        prefix_filter = filter.get("url_prefix")
        method_filter = filter.get("method")

        if bp_filter is not None:
            routes = [r for r in routes if r.blueprint == bp_filter]
        if prefix_filter is not None:
            routes = [r for r in routes if r.url.startswith(prefix_filter)]
        if method_filter is not None:
            routes = [r for r in routes if method_filter.upper() in r.methods]

    route_list = [
        {
            "url": r.url,
            "methods": list(r.methods),
            "endpoint": r.endpoint,
            "view_function": r.view.name,
            "blueprint": r.blueprint,
            "definition": {"file": r.definition.file, "line": r.definition.line},
            "decorators": [d.name for d in r.view.decorators],
        }
        for r in routes
    ]

    return envelope(
        "list_routes",
        {
            "routes": route_list,
            "total": len(route_list),
            "filtered_from": total_all,
        },
        warnings=list(index.warnings),
    )
