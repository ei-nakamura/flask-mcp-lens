from __future__ import annotations

from typing import Any, Literal

from flask_mcp_lens.auth.whitelist import (
    AUTH_FUNCTION_NAME_PATTERNS,
    BUILTIN_AUTH_DECORATORS,
)
from flask_mcp_lens.config import Config
from flask_mcp_lens.models import AuthConfidence, AuthSignal, Route, RouteAuthEvaluation

_CONFIDENCE_RANK: dict[AuthConfidence, int] = {
    "none": 0, "low": 1, "medium": 2, "high": 3
}


class AuthDetector:
    def evaluate(
        self,
        route: Route,
        hooks_by_scope: dict[str, list[Any]],
        config: Config,
    ) -> RouteAuthEvaluation:
        signals: list[AuthSignal] = []
        decorator_set = BUILTIN_AUTH_DECORATORS | set(config.auth.extra_decorators)
        blacklist = set(config.auth.blacklist_decorators)

        for d in route.view.decorators:
            bare_name = d.name.split(".")[-1]
            if bare_name in blacklist:
                continue
            if bare_name in decorator_set:
                kind: Literal["user_declared", "decorator"] = (
                    "user_declared"
                    if bare_name in config.auth.extra_decorators
                    else "decorator"
                )
                signals.append(AuthSignal(
                    kind=kind, name=d.name,
                    location=d.location, confidence="high",
                ))

        bp_key = f"blueprint:{route.blueprint}"
        applicable_hooks = (
            hooks_by_scope.get("app", []) + hooks_by_scope.get(bp_key, [])
        )
        for hook in applicable_hooks:
            if getattr(hook, "contains_abort_401_or_403", False):
                signals.append(AuthSignal(
                    kind="before_request_abort",
                    name=hook.func_name,
                    location=hook.location,
                    confidence="medium",
                ))

        for d in route.view.decorators:
            bare_name = d.name.split(".")[-1].lower()
            if any(pat in bare_name for pat in AUTH_FUNCTION_NAME_PATTERNS):
                if bare_name not in decorator_set and bare_name not in blacklist:
                    signals.append(AuthSignal(
                        kind="function_name_heuristic",
                        name=d.name,
                        location=d.location,
                        confidence="low",
                    ))

        max_conf: AuthConfidence = max(
            (s.confidence for s in signals),
            default="none",
            key=lambda c: _CONFIDENCE_RANK[c],
        )
        return RouteAuthEvaluation(
            route_endpoint=route.endpoint,
            signals=tuple(signals),
            max_confidence=max_conf,
        )
