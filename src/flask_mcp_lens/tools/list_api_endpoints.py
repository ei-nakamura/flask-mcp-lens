from __future__ import annotations

from typing import Any

from flask_mcp_lens.tools import envelope, get_manager

_API_URL_PREFIXES = ("/api", "/v1", "/v2", "/v3")


def list_api_endpoints(include: list[str] | None = None) -> dict[str, Any]:
    index = get_manager().get()
    use_all = not include

    endpoints = []
    for route in index.routes:
        matched: list[str] = []

        # json_response: source_excerpt に jsonify が含まれるか（簡易）
        if use_all or "json_response" in (include or []):
            excerpt = route.view.source_excerpt
            if "jsonify" in excerpt or "json_response" in excerpt:
                matched.append("json_response")

        # url_prefix_api
        if use_all or "url_prefix_api" in (include or []):
            if any(route.url.startswith(p) for p in _API_URL_PREFIXES):
                matched.append("url_prefix_api")

        if matched:
            endpoints.append({
                "url": route.url,
                "methods": list(route.methods),
                "endpoint": route.endpoint,
                "matched_signals": matched,
            })

    return envelope(
        "list_api_endpoints",
        {"endpoints": endpoints, "total": len(endpoints)},
        warnings=list(index.warnings),
    )
