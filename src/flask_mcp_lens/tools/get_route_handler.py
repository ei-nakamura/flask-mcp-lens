from __future__ import annotations

from typing import Any

from flask_mcp_lens import urlmap
from flask_mcp_lens.tools import envelope, get_manager


def get_route_handler(url: str, method: str = "GET") -> dict[str, Any]:
    index = get_manager().get()
    method = method.upper()

    matched = [
        r for r in index.routes
        if urlmap.match(r.url, r.methods, url, method)
    ]

    if not matched:
        suggestions = _find_suggestions(url, index.routes)
        return envelope(
            "get_route_handler",
            {"error": "no matching route", "suggestions": suggestions},
            warnings=list(index.warnings),
        )

    extra_warnings: list[str] = list(index.warnings)
    if len(matched) > 1:
        extra_warnings.append(
            f"同一URL+methodに複数ルートがマッチ: {url} {method}"
        )

    results = []
    for route in matched:
        app_hooks = [
            {
                "function_name": h.function_name,
                "file": h.location.file,
                "line": h.location.line,
            }
            for h in index.before_request_hooks
            if h.scope == "app"
        ]
        bp_hooks: list[dict[str, Any]] = []
        if route.blueprint:
            bp_hooks = [
                {
                    "function_name": h.function_name,
                    "file": h.location.file,
                    "line": h.location.line,
                }
                for h in index.before_request_hooks
                if h.scope == f"blueprint:{route.blueprint}"
            ]

        execution_chain = app_hooks + bp_hooks

        view = route.view
        source_excerpt: str | None = (
            view.source_excerpt if view.source_excerpt else None
        )

        results.append({
            "url": route.url,
            "methods": list(route.methods),
            "endpoint": route.endpoint,
            "blueprint": route.blueprint,
            "execution_chain": {
                "before_request_hooks": execution_chain,
                "decorators": [d.name for d in view.decorators],
                "view_function": {
                    "name": view.name,
                    "file": view.location.file,
                    "line": view.location.line,
                    "source_excerpt": source_excerpt,
                },
            },
        })

    data = results[0] if len(results) == 1 else {"routes": results}
    return envelope("get_route_handler", data, warnings=extra_warnings)


def _find_suggestions(url: str, routes: tuple[Any, ...]) -> list[dict[str, Any]]:
    def common_prefix_len(a: str, b: str) -> int:
        n = min(len(a), len(b))
        i = 0
        while i < n and a[i] == b[i]:
            i += 1
        return i

    scored = sorted(
        routes,
        key=lambda r: common_prefix_len(r.url, url),
        reverse=True,
    )[:3]

    return [
        {
            "url": r.url,
            "methods": list(r.methods),
            "endpoint": r.endpoint,
        }
        for r in scored
    ]
