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

    auth_eval_by_endpoint = {e.route_endpoint: e for e in index.auth_evaluations}

    route_list = []
    for r in routes:
        eval_ = auth_eval_by_endpoint.get(r.endpoint)
        if eval_ and eval_.signals:
            primary = max(
                eval_.signals,
                key=lambda s: {"high": 3, "medium": 2, "low": 1, "none": 0}[
                    s.confidence
                ],
            )
            auth_signal: dict[str, Any] | None = {
                "max_confidence": eval_.max_confidence,
                "primary_kind": primary.kind,
                "primary_name": primary.name,
            }
        elif eval_:
            auth_signal = {
                "max_confidence": "none", "primary_kind": None, "primary_name": None
            }
        else:
            auth_signal = None

        route_list.append({
            "url": r.url,
            "methods": list(r.methods),
            "endpoint": r.endpoint,
            "view_function": r.view.name,
            "blueprint": r.blueprint,
            "definition": {"file": r.definition.file, "line": r.definition.line},
            "decorators": [d.name for d in r.view.decorators],
            "auth_signal": auth_signal,
        })

    return envelope(
        "list_routes",
        {
            "routes": route_list,
            "total": len(route_list),
            "filtered_from": total_all,
        },
        warnings=list(index.warnings),
    )
