from __future__ import annotations

import time
from pathlib import Path
from typing import Optional

from flask_mcp_lens.analyzer.ast_visitor import FileRawNodes, RawBlueprint
from flask_mcp_lens.models import (
    AppFactoryCandidate,
    BeforeRequestHook,
    BlueprintDef,
    BlueprintRegistration,
    Decorator,
    Route,
    RouteIndex,
    SourceLoc,
    ViewFunction,
)


def resolve(
    file_nodes: list[FileRawNodes],
    project_root: Path,
    file_mtimes: dict[str, float] | None = None,
) -> RouteIndex:
    """Resolve RawNodes from all files into a RouteIndex."""
    warnings: list[str] = []

    # ── Blueprint collection ────────────────────────────────────────────────
    # bp_name → (var_name, file_str, url_prefix, url_prefix_dynamic, location)
    bp_info: dict[str, tuple[str, str, Optional[str], bool, SourceLoc]] = {}
    # (file, var_name) → RawBlueprint
    bp_by_file_var: dict[tuple[str, str], RawBlueprint] = {}

    for fn in file_nodes:
        for raw_bp in fn.blueprints:
            bp_by_file_var[(fn.file, raw_bp.var_name)] = raw_bp
            if raw_bp.bp_name not in bp_info:
                bp_info[raw_bp.bp_name] = (
                    raw_bp.var_name, fn.file,
                    raw_bp.url_prefix, raw_bp.url_prefix_dynamic,
                    raw_bp.location,
                )
            else:
                warnings.append(
                    f"Blueprint 名 '{raw_bp.bp_name}' が複数定義されています"
                    f" ({fn.file}:{raw_bp.location.line})"
                )

    # var_name → bp_name (first match across all files, for cross-file lookup)
    var_to_bp_name: dict[str, str] = {}
    for (_, var_name), raw_bp in bp_by_file_var.items():
        if var_name not in var_to_bp_name:
            var_to_bp_name[var_name] = raw_bp.bp_name

    # file → app instance var names
    app_vars_per_file: dict[str, set[str]] = {
        fn.file: {inst.var_name for inst in fn.app_instances}
        for fn in file_nodes
    }

    # ── register_blueprint resolution ─────────────────────────────────────
    bp_registrations: dict[str, list[BlueprintRegistration]] = {n: [] for n in bp_info}
    bp_parent: dict[str, str] = {}

    for fn in file_nodes:
        file_bp_map = {raw_bp.var_name: raw_bp.bp_name for raw_bp in fn.blueprints}
        file_app_vars = app_vars_per_file.get(fn.file, set())

        for reg in fn.register_blueprints:
            # Resolve child bp name
            child_bp = (
                file_bp_map.get(reg.child_var) or var_to_bp_name.get(reg.child_var)
            )
            if child_bp is None:
                continue

            # Warn on dynamic url_prefix override
            if reg.url_prefix_override_dynamic:
                warnings.append(
                    f"動的 url_prefix 検出: {fn.file}:{reg.location.line}"
                )

            bp_reg = BlueprintRegistration(
                location=reg.location,
                url_prefix_override=reg.url_prefix_override,
            )
            if child_bp not in bp_registrations:
                bp_registrations[child_bp] = []
            bp_registrations[child_bp].append(bp_reg)

            # Determine parent type
            if reg.parent_var not in file_app_vars:
                parent_bp = (
                    file_bp_map.get(reg.parent_var)
                    or var_to_bp_name.get(reg.parent_var)
                )
                if parent_bp:
                    if child_bp in bp_parent and bp_parent[child_bp] != parent_bp:
                        warnings.append(
                            f"Blueprint '{child_bp}' の親が複数定義されています"
                        )
                    else:
                        bp_parent[child_bp] = parent_bp

    # Warn on dynamic url_prefix in Blueprint definitions
    for bp_name, (_, _, _, is_dynamic, loc) in bp_info.items():
        if is_dynamic:
            warnings.append(f"動的 url_prefix 検出: {loc.file}:{loc.line}")

    # ── nesting depth check ────────────────────────────────────────────────
    def _depth(name: str, seen: set[str]) -> int:
        if name in seen:
            return 0
        seen.add(name)
        parent = bp_parent.get(name)
        return 1 + (_depth(parent, seen) if parent else 0)

    for bp_name in bp_info:
        if _depth(bp_name, set()) > 3:
            warnings.append(
                f"Blueprint '{bp_name}' の入れ子が3段以上です"
                "（Phase 1 では2段まで対応）"
            )

    # ── url_prefix computation (memoized) ──────────────────────────────────
    _prefix_cache: dict[str, str] = {}

    def _full_prefix(name: str, seen: set[str]) -> str:
        if name in _prefix_cache:
            return _prefix_cache[name]
        if name in seen or name not in bp_info:
            return ""
        seen.add(name)

        _, _, own_prefix, _, _ = bp_info[name]
        own = own_prefix or ""

        # Registration url_prefix_override takes precedence
        regs = bp_registrations.get(name, [])
        if regs and regs[0].url_prefix_override is not None:
            own = regs[0].url_prefix_override

        parent = bp_parent.get(name)
        result = (_full_prefix(parent, seen) if parent else "") + own
        _prefix_cache[name] = result
        return result

    # ── app factory candidates ─────────────────────────────────────────────
    app_factories: list[AppFactoryCandidate] = []
    seen_factory_names: set[str] = set()

    for fn in file_nodes:
        for inst in fn.app_instances:
            if inst.is_factory and inst.factory_func_name:
                fname = inst.factory_func_name
                if fname in seen_factory_names:
                    continue
                seen_factory_names.add(fname)
                confidence: str = (
                    "high" if fname in ("create_app", "make_app", "app_factory")
                    else "medium"
                )
                app_factories.append(AppFactoryCandidate(
                    kind="factory_function",
                    name=fname,
                    location=inst.location,
                    params=tuple(inst.params),
                    confidence=confidence,  # type: ignore[arg-type]
                ))
            else:
                confidence = "high" if inst.var_name == "app" else "medium"
                app_factories.append(AppFactoryCandidate(
                    kind="module_level_app",
                    name=inst.var_name,
                    location=inst.location,
                    params=(),
                    confidence=confidence,  # type: ignore[arg-type]
                ))

    if not app_factories:
        warnings.append("Flask app 未検出")

    selected_factory = _select_factory(app_factories)

    # ── routes ────────────────────────────────────────────────────────────
    routes: list[Route] = []

    for fn in file_nodes:
        file_bp_map = {raw_bp.var_name: raw_bp.bp_name for raw_bp in fn.blueprints}

        for raw_route in fn.routes:
            route_bp: str | None = file_bp_map.get(raw_route.owner_var)
            prefix = _full_prefix(route_bp, set()) if route_bp else ""
            full_url = prefix + raw_route.url

            if raw_route.endpoint:
                endpoint = raw_route.endpoint
            elif route_bp:
                endpoint = f"{route_bp}.{raw_route.func_name}"
            else:
                endpoint = raw_route.func_name

            decorators = tuple(
                Decorator(name=dec_name, location=raw_route.func_loc)
                for dec_name in raw_route.decorators_all
            )
            view = ViewFunction(
                name=raw_route.func_name,
                qualname=raw_route.func_name,
                location=raw_route.func_loc,
                decorators=decorators,
                source_excerpt="\n".join(raw_route.source_lines),
            )
            routes.append(Route(
                url=full_url,
                methods=tuple(raw_route.methods),
                endpoint=endpoint,
                blueprint=route_bp,
                view=view,
                definition=raw_route.decorator_loc,
            ))

        for raw_aur in fn.add_url_rules:
            if raw_aur.view_func_name is None:
                warnings.append(
                    f"{fn.file}:{raw_aur.location.line}:"
                    " add_url_rule の view_func が動的（解決不能）、スキップ"
                )
                continue

            bp_name_aur: str | None = file_bp_map.get(raw_aur.owner_var)
            prefix = _full_prefix(bp_name_aur, set()) if bp_name_aur else ""
            full_url = prefix + raw_aur.rule

            if raw_aur.endpoint:
                endpoint = raw_aur.endpoint
            elif bp_name_aur:
                endpoint = f"{bp_name_aur}.{raw_aur.view_func_name}"
            else:
                endpoint = raw_aur.view_func_name

            view = ViewFunction(
                name=raw_aur.view_func_name,
                qualname=raw_aur.view_func_name,
                location=raw_aur.location,
                decorators=(),
                source_excerpt="",
            )
            routes.append(Route(
                url=full_url,
                methods=tuple(raw_aur.methods),
                endpoint=endpoint,
                blueprint=bp_name_aur,
                view=view,
                definition=raw_aur.location,
            ))

    # ── before_request hooks ───────────────────────────────────────────────
    before_request_hooks: list[BeforeRequestHook] = []

    for fn in file_nodes:
        file_bp_map = {raw_bp.var_name: raw_bp.bp_name for raw_bp in fn.blueprints}

        for raw_br in fn.before_requests:
            bp_name_br: str | None = file_bp_map.get(raw_br.owner_var)
            scope = f"blueprint:{bp_name_br}" if bp_name_br else "app"
            before_request_hooks.append(BeforeRequestHook(
                function_name=raw_br.func_name,
                location=raw_br.location,
                scope=scope,
            ))

    # ── BlueprintDef objects ───────────────────────────────────────────────
    blueprint_defs: list[BlueprintDef] = []
    for bp_name, (_, _, url_prefix, _, loc) in bp_info.items():
        blueprint_defs.append(BlueprintDef(
            name=bp_name,
            file=loc,
            url_prefix=url_prefix,
            parent=bp_parent.get(bp_name),
            registrations=tuple(bp_registrations.get(bp_name, [])),
        ))

    return RouteIndex(
        project_root=project_root.as_posix(),
        analyzed_at=time.time(),
        file_mtimes=file_mtimes or {},
        app_factories=tuple(app_factories),
        selected_factory=selected_factory,
        blueprints=tuple(blueprint_defs),
        routes=tuple(routes),
        before_request_hooks=tuple(before_request_hooks),
        warnings=tuple(sorted(set(warnings))),
    )


def _select_factory(factories: list[AppFactoryCandidate]) -> int:
    if not factories:
        return 0
    for i, c in enumerate(factories):
        if c.kind == "module_level_app" and c.name == "app":
            return i
    for i, c in enumerate(factories):
        if c.kind == "factory_function" and c.name == "create_app":
            return i
    order = {"high": 0, "medium": 1, "low": 2}
    return min(range(len(factories)), key=lambda i: order[factories[i].confidence])
