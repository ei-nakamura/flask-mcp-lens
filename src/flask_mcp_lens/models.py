from __future__ import annotations

from dataclasses import dataclass, field
from typing import Literal, Optional


@dataclass(frozen=True)
class SourceLoc:
    file: str
    line: int
    col: int = 0


@dataclass(frozen=True)
class Decorator:
    name: str
    location: SourceLoc


@dataclass(frozen=True)
class BeforeRequestHook:
    function_name: str
    location: SourceLoc
    scope: str


@dataclass(frozen=True)
class ViewFunction:
    name: str
    qualname: str
    location: SourceLoc
    decorators: tuple[Decorator, ...]
    source_excerpt: str


@dataclass(frozen=True)
class Route:
    url: str
    methods: tuple[str, ...]
    endpoint: str
    blueprint: Optional[str]
    view: ViewFunction
    definition: SourceLoc


@dataclass(frozen=True)
class BlueprintRegistration:
    location: SourceLoc
    url_prefix_override: Optional[str]


@dataclass(frozen=True)
class BlueprintDef:
    name: str
    file: SourceLoc
    url_prefix: Optional[str]
    parent: Optional[str]
    registrations: tuple[BlueprintRegistration, ...]


@dataclass(frozen=True)
class AppFactoryCandidate:
    kind: Literal["factory_function", "module_level_app"]
    name: str
    location: SourceLoc
    params: tuple[str, ...]
    confidence: Literal["high", "medium", "low"]


AuthConfidence = Literal["high", "medium", "low", "none"]


@dataclass(frozen=True)
class AuthSignal:
    kind: Literal[
        "decorator", "before_request_abort", "function_name_heuristic", "user_declared"
    ]
    name: str
    location: SourceLoc
    confidence: AuthConfidence


@dataclass(frozen=True)
class RouteAuthEvaluation:
    route_endpoint: str
    signals: tuple[AuthSignal, ...]
    max_confidence: AuthConfidence


@dataclass(frozen=True)
class ExtensionInfo:
    name: str
    package: str
    declared_in: tuple[str, ...]
    imported_in: tuple[SourceLoc, ...]
    initialized_at: Optional[SourceLoc]
    confidence: Literal["high", "medium", "low"]
    config: dict[str, object]


@dataclass(frozen=True)
class BlueprintRegistrationStatus:
    blueprint: str
    status: Literal["registered", "registered_dynamic", "unregistered"]
    locations: tuple[SourceLoc, ...]


@dataclass(frozen=True)
class RouteIndex:
    project_root: str
    analyzed_at: float
    file_mtimes: dict[str, float]
    app_factories: tuple[AppFactoryCandidate, ...]
    selected_factory: int
    blueprints: tuple[BlueprintDef, ...]
    routes: tuple[Route, ...]
    before_request_hooks: tuple[BeforeRequestHook, ...]
    warnings: tuple[str, ...]
    schema_version: str = "2"
    auth_evaluations: tuple[RouteAuthEvaluation, ...] = field(default=())
    extensions: tuple[ExtensionInfo, ...] = field(default=())
    blueprint_status: tuple[BlueprintRegistrationStatus, ...] = field(default=())
