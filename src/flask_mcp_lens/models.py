from __future__ import annotations

from dataclasses import dataclass
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
    schema_version: str = "1"
