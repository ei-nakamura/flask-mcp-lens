from __future__ import annotations

from typing import Any

from flask_mcp_lens.tools import envelope, get_manager


def find_potentially_unprotected_routes() -> dict[str, Any]:
    index = get_manager().get()
    eval_by_endpoint = {e.route_endpoint: e for e in index.auth_evaluations}

    definitely: list[dict[str, Any]] = []
    likely: list[dict[str, Any]] = []
    ambiguous: list[dict[str, Any]] = []
    protected_count = 0

    for route in index.routes:
        eval_ = eval_by_endpoint.get(route.endpoint)
        conf = eval_.max_confidence if eval_ else "none"
        signals = [
            {"kind": s.kind, "name": s.name, "confidence": s.confidence}
            for s in (eval_.signals if eval_ else ())
        ]
        entry = {
            "url": route.url,
            "methods": list(route.methods),
            "endpoint": route.endpoint,
            "definition": {
                "file": route.definition.file, "line": route.definition.line
            },
            "signals": signals,
        }
        if conf == "none":
            entry["rationale"] = "認証シグナル一切なし"
            definitely.append(entry)
        elif conf == "low":
            primary = signals[0]["name"] if signals else "?"
            entry["rationale"] = f"関数名ヒューリスティックのみ: {primary}"
            likely.append(entry)
        elif conf == "medium":
            entry["rationale"] = "before_request abort(401/403) のみ検出"
            ambiguous.append(entry)
        else:
            protected_count += 1

    total = len(index.routes)
    return envelope(
        "find_potentially_unprotected_routes",
        {
            "definitely_unprotected": definitely,
            "likely_unprotected": likely,
            "ambiguous": ambiguous,
            "summary": {
                "total_routes": total,
                "definitely_unprotected": len(definitely),
                "likely_unprotected": len(likely),
                "ambiguous": len(ambiguous),
                "high_confidence_protected": protected_count,
            },
        },
        warnings=list(index.warnings),
    )
