from __future__ import annotations

from collections import defaultdict
from typing import Any

from flask_mcp_lens.tools import envelope, get_manager

_EXT_DECORATORS = {
    "login_required": "flask_login",
    "fresh_login_required": "flask_login",
    "jwt_required": "flask_jwt_extended",
    "jwt_optional": "flask_jwt_extended",
}


def list_auth_strategies() -> dict[str, Any]:
    index = get_manager().get()
    # kind+name → {endpoints, scope}
    strategy_map: dict[tuple[str, str], dict[str, Any]] = defaultdict(
        lambda: {"routes": [], "scope": None}
    )

    for eval_ in index.auth_evaluations:
        for sig in eval_.signals:
            key = (sig.kind, sig.name)
            strategy_map[key]["routes"].append(eval_.route_endpoint)
            if sig.kind == "before_request_abort":
                # scope is on the hook, not on the signal; use name as heuristic
                pass

    strategies = []
    for (kind, name), info in strategy_map.items():
        routes = info["routes"]
        entry: dict[str, Any] = {
            "kind": kind,
            "name": name,
            "source_extension": _EXT_DECORATORS.get(name.split(".")[-1]),
            "applied_routes_count": len(routes),
            "applied_routes": routes[:50],
        }
        strategies.append(entry)

    return envelope(
        "list_auth_strategies",
        {"strategies": strategies},
        warnings=list(index.warnings),
    )
