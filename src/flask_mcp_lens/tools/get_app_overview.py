from __future__ import annotations

from typing import Any

from flask_mcp_lens.tools import envelope, get_manager


def get_app_overview() -> dict[str, Any]:
    index = get_manager().get()

    if index.app_factories and index.selected_factory is not None:
        selected_idx = index.selected_factory
        if 0 <= selected_idx < len(index.app_factories):
            factory = index.app_factories[selected_idx]
            app_factory_data: dict[str, Any] | None = {
                "file": factory.location.file,
                "line": factory.location.line,
                "kind": factory.kind,
                "name": factory.name,
            }
            factory_loc = f"{factory.location.file}:{factory.location.line}"
            factory_md = f"`{factory.name}` (`{factory_loc}`)"
        else:
            app_factory_data = None
            factory_md = "not found"
    else:
        app_factory_data = None
        factory_md = "not found"

    blueprint_count = len(index.blueprints)
    route_count = len(index.routes)

    summary_markdown = (
        f"## App Overview\n\n"
        f"- App factory: {factory_md}\n"
        f"- Blueprints: {blueprint_count}\n"
        f"- Routes: {route_count}\n\n"
        f"*Authentication detection: Phase 2+*"
    )

    return envelope(
        "get_app_overview",
        {
            "app_factory": app_factory_data,
            "blueprint_count": blueprint_count,
            "route_count": route_count,
            "extensions_detected": [],          # Phase 2
            "auth_strategies_summary": None,    # Phase 2
            "summary_markdown": summary_markdown,
        },
        warnings=list(index.warnings),
    )
