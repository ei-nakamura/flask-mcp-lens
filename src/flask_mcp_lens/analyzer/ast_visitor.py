from __future__ import annotations

import ast
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Optional

from flask_mcp_lens.analyzer.imports import AliasMap
from flask_mcp_lens.models import SourceLoc

HTTP_METHODS = frozenset({"get", "post", "put", "delete", "patch", "head", "options"})


@dataclass
class RawRoute:
    url: str
    methods: list[str]
    endpoint: Optional[str]
    func_name: str
    decorator_loc: SourceLoc
    func_loc: SourceLoc
    decorators_all: list[str]   # non-route decorator names (dotted)
    source_lines: list[str]     # function definition line + next 5
    owner_var: str              # "app" or bp variable name
    body_calls: tuple[str, ...] = ()


@dataclass
class RawBlueprint:
    var_name: str               # variable name in source (e.g. "users_api")
    bp_name: str                # Blueprint(name=...) argument
    url_prefix: Optional[str]   # None if absent or dynamic
    url_prefix_dynamic: bool    # True when url_prefix kwarg exists but is non-constant
    location: SourceLoc


@dataclass
class RawRegisterBlueprint:
    parent_var: str             # app or parent bp variable name
    child_var: str              # child bp variable name
    url_prefix_override: Optional[str]
    url_prefix_override_dynamic: bool
    location: SourceLoc


@dataclass
class RawAddUrlRule:
    rule: str
    view_func_name: Optional[str]   # None for dynamic (lambda etc.)
    methods: list[str]
    endpoint: Optional[str]
    owner_var: str
    location: SourceLoc


@dataclass
class RawBeforeRequest:
    func_name: str
    owner_var: str              # "app" or bp variable name
    location: SourceLoc


@dataclass
class RawAppInstance:
    var_name: str
    location: SourceLoc
    is_factory: bool            # True if inside a function body
    factory_func_name: Optional[str]
    params: list[str]           # factory function parameter names


@dataclass
class FileRawNodes:
    file: str                   # project-root-relative path, forward slash
    app_instances: list[RawAppInstance]
    blueprints: list[RawBlueprint]
    routes: list[RawRoute]
    add_url_rules: list[RawAddUrlRule]
    register_blueprints: list[RawRegisterBlueprint]
    before_requests: list[RawBeforeRequest]


class FlaskASTVisitor(ast.NodeVisitor):
    def __init__(self, filepath: str, source: str, alias_map: AliasMap) -> None:
        self.filepath = filepath
        self.alias_map = alias_map
        self._lines = source.splitlines()
        self._func_stack: list[ast.FunctionDef | ast.AsyncFunctionDef] = []

        self.app_instances: list[RawAppInstance] = []
        self.blueprints: list[RawBlueprint] = []
        self.routes: list[RawRoute] = []
        self.add_url_rules: list[RawAddUrlRule] = []
        self.register_blueprints: list[RawRegisterBlueprint] = []
        self.before_requests: list[RawBeforeRequest] = []
        self._pending_method_views: dict[str, list[dict[str, Any]]] = {}

    # ── helpers ────────────────────────────────────────────────────────────

    def _loc(self, node: ast.AST) -> SourceLoc:
        return SourceLoc(file=self.filepath, line=getattr(node, "lineno", 0))

    def _str_const(self, node: ast.expr) -> Optional[str]:
        if isinstance(node, ast.Constant) and isinstance(node.value, str):
            return node.value
        return None

    def _str_list(self, node: ast.expr) -> Optional[list[str]]:
        if isinstance(node, (ast.List, ast.Tuple)):
            result = []
            for elt in node.elts:
                v = self._str_const(elt)
                if v is None:
                    return None
                result.append(v)
            return result
        return None

    def _kwarg(self, node: ast.Call, name: str) -> Optional[ast.expr]:
        for kw in node.keywords:
            if kw.arg == name:
                return kw.value
        return None

    def _resolve_call_name(self, node: ast.Call) -> Optional[str]:
        """Return canonical Flask class name for a Call, or None."""
        func = node.func
        if isinstance(func, ast.Name):
            return self.alias_map.resolve(func.id)
        if isinstance(func, ast.Attribute) and isinstance(func.value, ast.Name):
            dotted = f"{func.value.id}.{func.attr}"
            resolved = self.alias_map.resolve(dotted)
            if resolved != dotted:
                return resolved
        return None

    def _decorator_attr(self, dec: ast.expr) -> tuple[Optional[str], Optional[str]]:
        """Return (method_attr, owner_var) for a decorator."""
        func = dec.func if isinstance(dec, ast.Call) else dec
        if isinstance(func, ast.Attribute) and isinstance(func.value, ast.Name):
            return func.attr, func.value.id
        if isinstance(func, ast.Name):
            return func.id, None
        return None, None

    def _decorator_full_name(self, dec: ast.expr) -> Optional[str]:
        func = dec.func if isinstance(dec, ast.Call) else dec
        parts: list[str] = []
        cur: ast.expr = func
        while isinstance(cur, ast.Attribute):
            parts.append(cur.attr)
            cur = cur.value
        if isinstance(cur, ast.Name):
            parts.append(cur.id)
        return ".".join(reversed(parts)) if parts else None

    def _excerpt(self, node: ast.FunctionDef | ast.AsyncFunctionDef) -> list[str]:
        start = node.lineno - 1
        return self._lines[start : start + 6]

    def _collect_body_calls(
        self, func_node: ast.FunctionDef | ast.AsyncFunctionDef
    ) -> tuple[str, ...]:
        calls = []
        for node in ast.walk(func_node):
            if isinstance(node, ast.Call):
                if isinstance(node.func, ast.Name):
                    calls.append(node.func.id)
                elif isinstance(node.func, ast.Attribute):
                    if isinstance(node.func.value, ast.Name):
                        calls.append(f"{node.func.value.id}.{node.func.attr}")
                    else:
                        calls.append(f"{ast.dump(node.func.value)}.{node.func.attr}")
        return tuple(calls)

    def _is_method_view(self, node: ast.ClassDef) -> bool:
        for base in node.bases:
            name = ""
            if isinstance(base, ast.Name):
                name = base.id
            elif isinstance(base, ast.Attribute):
                name = base.attr
            if name in ("MethodView", "View"):
                return True
        return False

    # ── visitors ───────────────────────────────────────────────────────────

    def visit_Import(self, node: ast.Import) -> None:
        self.generic_visit(node)

    def visit_ImportFrom(self, node: ast.ImportFrom) -> None:
        self.generic_visit(node)

    def visit_Assign(self, node: ast.Assign) -> None:
        if isinstance(node.value, ast.Call):
            canonical = self._resolve_call_name(node.value)
            targets = [t.id for t in node.targets if isinstance(t, ast.Name)]

            if canonical == "Flask" and targets:
                var_name = targets[0]
                ctx_func = self._func_stack[-1] if self._func_stack else None
                self.app_instances.append(RawAppInstance(
                    var_name=var_name,
                    location=self._loc(node),
                    is_factory=ctx_func is not None,
                    factory_func_name=ctx_func.name if ctx_func else None,
                    params=[a.arg for a in ctx_func.args.args] if ctx_func else [],
                ))

            elif canonical == "Blueprint" and targets:
                var_name = targets[0]
                call = node.value

                bp_name: Optional[str] = None
                if call.args:
                    bp_name = self._str_const(call.args[0])
                if bp_name is None:
                    kw = self._kwarg(call, "name")
                    if kw is not None:
                        bp_name = self._str_const(kw)
                if bp_name is None:
                    bp_name = var_name

                url_prefix: Optional[str] = None
                url_prefix_dynamic = False
                up_kw = self._kwarg(call, "url_prefix")
                if up_kw is not None:
                    val = self._str_const(up_kw)
                    if val is not None:
                        url_prefix = val
                    else:
                        url_prefix_dynamic = True

                self.blueprints.append(RawBlueprint(
                    var_name=var_name,
                    bp_name=bp_name,
                    url_prefix=url_prefix,
                    url_prefix_dynamic=url_prefix_dynamic,
                    location=self._loc(node),
                ))

        self.generic_visit(node)

    def _visit_funcdef(self, node: ast.FunctionDef | ast.AsyncFunctionDef) -> None:
        route_decs: list[tuple[ast.expr, str]] = []
        other_dec_names: list[str] = []
        before_request_owner: Optional[str] = None

        for dec in node.decorator_list:
            method, owner = self._decorator_attr(dec)
            if method == "route":
                route_decs.append((dec, owner or "app"))
            elif method == "before_request":
                before_request_owner = owner or "app"
            else:
                full = self._decorator_full_name(dec)
                if full:
                    other_dec_names.append(full)

        if before_request_owner is not None:
            self.before_requests.append(RawBeforeRequest(
                func_name=node.name,
                owner_var=before_request_owner,
                location=self._loc(node),
            ))

        for dec_node, owner_var in route_decs:
            self._handle_route_dec(dec_node, owner_var, node, other_dec_names)

        self._func_stack.append(node)
        self.generic_visit(node)
        self._func_stack.pop()

    def _handle_route_dec(
        self,
        dec: ast.expr,
        owner_var: str,
        func_node: ast.FunctionDef | ast.AsyncFunctionDef,
        other_dec_names: list[str],
    ) -> None:
        if not isinstance(dec, ast.Call):
            return

        url: Optional[str] = None
        if dec.args:
            url = self._str_const(dec.args[0])
        if url is None:
            rule_kw = self._kwarg(dec, "rule")
            if rule_kw is not None:
                url = self._str_const(rule_kw)
        if url is None:
            return

        methods: list[str] = ["GET"]
        m_kw = self._kwarg(dec, "methods")
        if m_kw is not None:
            ml = self._str_list(m_kw)
            if ml:
                methods = sorted(m.upper() for m in ml)

        endpoint: Optional[str] = None
        ep_kw = self._kwarg(dec, "endpoint")
        if ep_kw is not None:
            endpoint = self._str_const(ep_kw)

        self.routes.append(RawRoute(
            url=url,
            methods=methods,
            endpoint=endpoint,
            func_name=func_node.name,
            decorator_loc=self._loc(dec),
            func_loc=self._loc(func_node),
            decorators_all=list(other_dec_names),
            source_lines=self._excerpt(func_node),
            owner_var=owner_var,
            body_calls=self._collect_body_calls(func_node),
        ))

    def visit_ClassDef(self, node: ast.ClassDef) -> None:
        if not self._is_method_view(node):
            self.generic_visit(node)
            return
        class_name = node.name
        class_decorators: list[str] = []
        for item in node.body:
            if isinstance(item, ast.Assign):
                for target in item.targets:
                    if isinstance(target, ast.Name) and target.id == "decorators":
                        if isinstance(item.value, ast.List):
                            for elt in item.value.elts:
                                if isinstance(elt, ast.Name):
                                    class_decorators.append(elt.id)
        for item in node.body:
            if isinstance(item, ast.FunctionDef) and item.name in HTTP_METHODS:
                self._pending_method_views.setdefault(class_name, []).append({
                    "method": item.name.upper(),
                    "func_node": item,
                    "class_decorators": class_decorators,
                })
        self.generic_visit(node)

    def visit_FunctionDef(self, node: ast.FunctionDef) -> None:
        self._visit_funcdef(node)

    def visit_AsyncFunctionDef(self, node: ast.AsyncFunctionDef) -> None:
        self._visit_funcdef(node)

    def visit_Call(self, node: ast.Call) -> None:
        if (isinstance(node.func, ast.Attribute)
                and isinstance(node.func.value, ast.Name)):
            attr = node.func.attr
            owner = node.func.value.id

            if attr == "add_url_rule":
                self._handle_add_url_rule(node, owner)
            elif attr == "register_blueprint":
                self._handle_register_blueprint(node, owner)
            elif attr == "before_request":
                # before_request(func) call form (not decorator)
                if node.args and isinstance(node.args[0], ast.Name):
                    self.before_requests.append(RawBeforeRequest(
                        func_name=node.args[0].id,
                        owner_var=owner,
                        location=self._loc(node),
                    ))

        self.generic_visit(node)

    def _handle_add_url_rule(self, node: ast.Call, owner_var: str) -> None:
        rule: Optional[str] = None
        if node.args:
            rule = self._str_const(node.args[0])
        if rule is None:
            kw = self._kwarg(node, "rule")
            if kw is not None:
                rule = self._str_const(kw)
        if rule is None:
            return

        # Determine view_func node (positional arg[2] or keyword)
        vf_node: Optional[ast.expr] = None
        if len(node.args) >= 3:
            vf_node = node.args[2]
        vf_kw = self._kwarg(node, "view_func")
        if vf_kw is not None:
            vf_node = vf_kw

        # Check for FooView.as_view("name") pattern
        if vf_node is not None and isinstance(vf_node, ast.Call):
            func = vf_node.func
            if (isinstance(func, ast.Attribute)
                    and func.attr == "as_view"
                    and isinstance(func.value, ast.Name)):
                view_class_name = func.value.id
                as_view_endpoint: Optional[str] = None
                if vf_node.args:
                    as_view_endpoint = self._str_const(vf_node.args[0])
                if as_view_endpoint is None:
                    name_kw = self._kwarg(vf_node, "name")
                    if name_kw is not None:
                        as_view_endpoint = self._str_const(name_kw)
                endpoint: Optional[str] = as_view_endpoint
                if endpoint is None:
                    ep_kw = self._kwarg(node, "endpoint")
                    if ep_kw is not None:
                        endpoint = self._str_const(ep_kw)
                for mv in self._pending_method_views.get(view_class_name, []):
                    method_func_node: ast.FunctionDef = mv["func_node"]
                    method_decorators = list(mv["class_decorators"])
                    for dec in method_func_node.decorator_list:
                        full = self._decorator_full_name(dec)
                        if full:
                            method_decorators.append(full)
                    qualname = f"{view_class_name}.{method_func_node.name}"
                    self.routes.append(RawRoute(
                        url=rule,
                        methods=[mv["method"]],
                        endpoint=endpoint,
                        func_name=qualname,
                        decorator_loc=self._loc(node),
                        func_loc=self._loc(method_func_node),
                        decorators_all=method_decorators,
                        source_lines=self._excerpt(method_func_node),
                        owner_var=owner_var,
                        body_calls=self._collect_body_calls(method_func_node),
                    ))
                return

        # Regular add_url_rule processing
        view_func_name: Optional[str] = None
        if vf_node is not None and isinstance(vf_node, ast.Name):
            view_func_name = vf_node.id

        endpoint2: Optional[str] = None
        if len(node.args) >= 2:
            endpoint2 = self._str_const(node.args[1])
        if endpoint2 is None:
            ep_kw = self._kwarg(node, "endpoint")
            if ep_kw is not None:
                endpoint2 = self._str_const(ep_kw)

        methods: list[str] = ["GET"]
        m_kw = self._kwarg(node, "methods")
        if m_kw is not None:
            ml = self._str_list(m_kw)
            if ml:
                methods = sorted(m.upper() for m in ml)

        self.add_url_rules.append(RawAddUrlRule(
            rule=rule,
            view_func_name=view_func_name,
            methods=methods,
            endpoint=endpoint2,
            owner_var=owner_var,
            location=self._loc(node),
        ))

    def _handle_register_blueprint(self, node: ast.Call, parent_var: str) -> None:
        if not node.args or not isinstance(node.args[0], ast.Name):
            return
        child_var = node.args[0].id

        url_prefix_override: Optional[str] = None
        url_prefix_override_dynamic = False
        up_kw = self._kwarg(node, "url_prefix")
        if up_kw is not None:
            val = self._str_const(up_kw)
            if val is not None:
                url_prefix_override = val
            else:
                url_prefix_override_dynamic = True

        self.register_blueprints.append(RawRegisterBlueprint(
            parent_var=parent_var,
            child_var=child_var,
            url_prefix_override=url_prefix_override,
            url_prefix_override_dynamic=url_prefix_override_dynamic,
            location=self._loc(node),
        ))


def visit_file(filepath: Path, project_root: Path) -> Optional[FileRawNodes]:
    """Parse a Python file and extract Flask-related AST nodes.

    Returns None on read error or SyntaxError.
    """
    try:
        source = filepath.read_text(encoding="utf-8")
    except (OSError, UnicodeDecodeError):
        return None

    try:
        tree = ast.parse(source, filename=str(filepath))
    except SyntaxError:
        return None

    rel = filepath.relative_to(project_root).as_posix()
    alias_map = AliasMap.build(tree)
    visitor = FlaskASTVisitor(rel, source, alias_map)
    visitor.visit(tree)

    return FileRawNodes(
        file=rel,
        app_instances=visitor.app_instances,
        blueprints=visitor.blueprints,
        routes=visitor.routes,
        add_url_rules=visitor.add_url_rules,
        register_blueprints=visitor.register_blueprints,
        before_requests=visitor.before_requests,
    )
