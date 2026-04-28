from __future__ import annotations

import dataclasses
import gzip
import json
import os
from pathlib import Path
from typing import Any, Optional

from flask_mcp_lens.models import (
    AppFactoryCandidate,
    AuthSignal,
    BeforeRequestHook,
    BlueprintDef,
    BlueprintRegistration,
    BlueprintRegistrationStatus,
    Decorator,
    ExtensionInfo,
    Route,
    RouteAuthEvaluation,
    RouteIndex,
    SourceLoc,
    ViewFunction,
)


def _to_dict(obj: Any) -> Any:
    if dataclasses.is_dataclass(obj) and not isinstance(obj, type):
        return {f.name: _to_dict(getattr(obj, f.name)) for f in dataclasses.fields(obj)}
    if isinstance(obj, (tuple, list)):
        return [_to_dict(v) for v in obj]
    if isinstance(obj, dict):
        return {k: _to_dict(v) for k, v in obj.items()}
    return obj


def _source_loc_from_dict(d: dict[str, Any]) -> SourceLoc:
    return SourceLoc(file=d["file"], line=d["line"], col=d.get("col", 0))


def _decorator_from_dict(d: dict[str, Any]) -> Decorator:
    return Decorator(name=d["name"], location=_source_loc_from_dict(d["location"]))


def _view_function_from_dict(d: dict[str, Any]) -> ViewFunction:
    return ViewFunction(
        name=d["name"],
        qualname=d["qualname"],
        location=_source_loc_from_dict(d["location"]),
        decorators=tuple(_decorator_from_dict(x) for x in d["decorators"]),
        source_excerpt=d["source_excerpt"],
    )


def _route_from_dict(d: dict[str, Any]) -> Route:
    return Route(
        url=d["url"],
        methods=tuple(d["methods"]),
        endpoint=d["endpoint"],
        blueprint=d.get("blueprint"),
        view=_view_function_from_dict(d["view"]),
        definition=_source_loc_from_dict(d["definition"]),
    )


def _blueprint_registration_from_dict(d: dict[str, Any]) -> BlueprintRegistration:
    return BlueprintRegistration(
        location=_source_loc_from_dict(d["location"]),
        url_prefix_override=d.get("url_prefix_override"),
    )


def _blueprint_def_from_dict(d: dict[str, Any]) -> BlueprintDef:
    return BlueprintDef(
        name=d["name"],
        file=_source_loc_from_dict(d["file"]),
        url_prefix=d.get("url_prefix"),
        parent=d.get("parent"),
        registrations=tuple(
            _blueprint_registration_from_dict(r) for r in d["registrations"]
        ),
    )


def _auth_signal_from_dict(d: dict[str, Any]) -> AuthSignal:
    return AuthSignal(
        kind=d["kind"],
        name=d["name"],
        location=_source_loc_from_dict(d["location"]),
        confidence=d["confidence"],
    )


def _route_auth_evaluation_from_dict(d: dict[str, Any]) -> RouteAuthEvaluation:
    return RouteAuthEvaluation(
        route_endpoint=d["route_endpoint"],
        signals=tuple(_auth_signal_from_dict(s) for s in d["signals"]),
        max_confidence=d["max_confidence"],
    )


def _extension_info_from_dict(d: dict[str, Any]) -> ExtensionInfo:
    return ExtensionInfo(
        name=d["name"],
        package=d["package"],
        declared_in=tuple(d["declared_in"]),
        imported_in=tuple(_source_loc_from_dict(x) for x in d.get("imported_in", [])),
        initialized_at=(
            _source_loc_from_dict(d["initialized_at"])
            if d.get("initialized_at") else None
        ),
        confidence=d["confidence"],
        config=d.get("config", {}),
    )


def _blueprint_registration_status_from_dict(
    d: dict[str, Any],
) -> BlueprintRegistrationStatus:
    return BlueprintRegistrationStatus(
        blueprint=d["blueprint"],
        status=d["status"],
        locations=tuple(_source_loc_from_dict(x) for x in d.get("locations", [])),
    )


def _before_request_hook_from_dict(d: dict[str, Any]) -> BeforeRequestHook:
    return BeforeRequestHook(
        function_name=d["function_name"],
        location=_source_loc_from_dict(d["location"]),
        scope=d["scope"],
    )


def _app_factory_candidate_from_dict(d: dict[str, Any]) -> AppFactoryCandidate:
    return AppFactoryCandidate(
        kind=d["kind"],
        name=d["name"],
        location=_source_loc_from_dict(d["location"]),
        params=tuple(d["params"]),
        confidence=d["confidence"],
    )


def _route_index_from_dict(d: dict[str, Any]) -> RouteIndex:
    return RouteIndex(
        schema_version=d.get("schema_version", "2"),
        project_root=d["project_root"],
        analyzed_at=d["analyzed_at"],
        file_mtimes=d["file_mtimes"],
        app_factories=tuple(
            _app_factory_candidate_from_dict(f) for f in d["app_factories"]
        ),
        selected_factory=d["selected_factory"],
        blueprints=tuple(_blueprint_def_from_dict(b) for b in d["blueprints"]),
        routes=tuple(_route_from_dict(r) for r in d["routes"]),
        before_request_hooks=tuple(
            _before_request_hook_from_dict(h) for h in d["before_request_hooks"]
        ),
        warnings=tuple(d["warnings"]),
        auth_evaluations=tuple(
            _route_auth_evaluation_from_dict(e)
            for e in d.get("auth_evaluations", [])
        ),
        extensions=tuple(
            _extension_info_from_dict(e) for e in d.get("extensions", [])
        ),
        blueprint_status=tuple(
            _blueprint_registration_status_from_dict(s)
            for s in d.get("blueprint_status", [])
        ),
    )


def save(index: RouteIndex, cache_path: Path) -> None:
    data = _to_dict(index)
    tmp_path = cache_path.parent / (cache_path.name + ".tmp")
    cache_path.parent.mkdir(parents=True, exist_ok=True)
    with gzip.open(tmp_path, "wt", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False)
    os.replace(tmp_path, cache_path)


def load(cache_path: Path) -> Optional[RouteIndex]:
    if not cache_path.exists():
        return None
    try:
        with gzip.open(cache_path, "rt", encoding="utf-8") as f:
            data = json.load(f)
        if data.get("schema_version") != "2":
            return None
        return _route_index_from_dict(data)
    except Exception:
        return None
