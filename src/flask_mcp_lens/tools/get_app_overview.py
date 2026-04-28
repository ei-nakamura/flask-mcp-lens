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

    extensions_detected = [e.name for e in index.extensions]

    registered_count = sum(
        1 for bs in index.blueprint_status
        if bs.status in ("registered", "registered_dynamic")
    )
    unregistered_count = sum(
        1 for bs in index.blueprint_status if bs.status == "unregistered"
    )

    if index.auth_evaluations:
        decorator_kinds = {"decorator", "user_declared"}
        before_request_kinds = {"before_request_abort"}
        decorator_names: set[str] = set()
        before_request_names: set[str] = set()
        high_conf_count = 0
        unprotected_count = 0
        ambiguous_count = 0

        for eval_ in index.auth_evaluations:
            if eval_.max_confidence == "high":
                high_conf_count += 1
                for s in eval_.signals:
                    if s.kind in decorator_kinds:
                        decorator_names.add(s.name.split(".")[-1])
                    elif s.kind in before_request_kinds:
                        before_request_names.add(s.name)
            elif eval_.max_confidence == "none":
                unprotected_count += 1
            elif eval_.max_confidence in ("low", "medium"):
                ambiguous_count += 1

        auth_strategies_summary: dict[str, Any] | None = {
            "decorator_based": len(decorator_names),
            "before_request_based": len(before_request_names),
            "high_confidence_protected_routes": high_conf_count,
            "definitely_unprotected_routes": unprotected_count,
            "ambiguous_routes": ambiguous_count,
        }
    else:
        auth_strategies_summary = None

    ext_str = ", ".join(extensions_detected) if extensions_detected else "none detected"
    summary_markdown = (
        f"## App Overview\n\n"
        f"- App factory: {factory_md}\n"
        f"- Blueprints: {blueprint_count}"
        f" ({registered_count} registered, {unregistered_count} unregistered)\n"
        f"- Routes: {route_count}\n"
        f"- Extensions: {ext_str}\n"
    )
    if auth_strategies_summary:
        summary_markdown += (
            f"- Auth: {auth_strategies_summary['high_confidence_protected_routes']}"
            " protected, "
            f"{auth_strategies_summary['definitely_unprotected_routes']} unprotected\n"
        )

    return envelope(
        "get_app_overview",
        {
            "app_factory": app_factory_data,
            "blueprint_count": blueprint_count,
            "registered_blueprint_count": registered_count,
            "unregistered_blueprint_count": unregistered_count,
            "route_count": route_count,
            "extensions_detected": extensions_detected,
            "auth_strategies_summary": auth_strategies_summary,
            "summary_markdown": summary_markdown,
        },
        warnings=list(index.warnings),
    )
