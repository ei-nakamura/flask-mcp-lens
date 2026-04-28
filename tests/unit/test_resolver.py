from pathlib import Path

from flask_mcp_lens.analyzer.ast_visitor import (
    FileRawNodes,
    RawAppInstance,
    RawBlueprint,
    RawRegisterBlueprint,
    RawRoute,
)
from flask_mcp_lens.analyzer.resolver import resolve
from flask_mcp_lens.models import SourceLoc


def _loc(file: str, line: int) -> SourceLoc:
    return SourceLoc(file=file, line=line)


def make_raw_nodes_nested_bp() -> list[FileRawNodes]:
    """Build FileRawNodes for a nested Blueprint structure:
    app registers api_v1 (/api/v1), api_v1 registers users_api (/users).
    users_api has GET / -> list_users.
    """
    app_instance = RawAppInstance(
        var_name="app",
        location=_loc("app.py", 2),
        is_factory=False,
        factory_func_name=None,
        params=[],
    )
    api_v1_bp = RawBlueprint(
        var_name="api_v1",
        bp_name="api_v1",
        url_prefix=None,
        url_prefix_dynamic=False,
        location=_loc("api/__init__.py", 2),
    )
    users_bp = RawBlueprint(
        var_name="users_api",
        bp_name="users_api",
        url_prefix=None,
        url_prefix_dynamic=False,
        location=_loc("api/users.py", 2),
    )
    reg_api = RawRegisterBlueprint(
        parent_var="app",
        child_var="api_v1",
        url_prefix_override="/api/v1",
        url_prefix_override_dynamic=False,
        location=_loc("app.py", 3),
    )
    reg_users = RawRegisterBlueprint(
        parent_var="api_v1",
        child_var="users_api",
        url_prefix_override="/users",
        url_prefix_override_dynamic=False,
        location=_loc("api/__init__.py", 3),
    )
    route = RawRoute(
        url="/",
        methods=["GET"],
        endpoint=None,
        func_name="list_users",
        decorator_loc=_loc("api/users.py", 4),
        func_loc=_loc("api/users.py", 5),
        decorators_all=[],
        source_lines=["def list_users():", "    return []"],
        owner_var="users_api",
    )
    return [
        FileRawNodes(
            file="app.py",
            app_instances=[app_instance],
            blueprints=[],
            routes=[],
            add_url_rules=[],
            register_blueprints=[reg_api],
            before_requests=[],
        ),
        FileRawNodes(
            file="api/__init__.py",
            app_instances=[],
            blueprints=[api_v1_bp],
            routes=[],
            add_url_rules=[],
            register_blueprints=[reg_users],
            before_requests=[],
        ),
        FileRawNodes(
            file="api/users.py",
            app_instances=[],
            blueprints=[users_bp],
            routes=[route],
            add_url_rules=[],
            register_blueprints=[],
            before_requests=[],
        ),
    ]


class TestNestedBlueprintUrlPrefix:
    def test_nested_prefix_concatenated(self):
        nodes = make_raw_nodes_nested_bp()
        index = resolve(nodes, project_root=Path("/tmp/proj"))
        urls = [r.url for r in index.routes]
        assert "/api/v1/users/" in urls

    def test_endpoint_auto_generated(self):
        nodes = make_raw_nodes_nested_bp()
        index = resolve(nodes, project_root=Path("/tmp/proj"))
        endpoints = [r.endpoint for r in index.routes]
        assert "users_api.list_users" in endpoints


class TestBlueprintNameConflict:
    def test_duplicate_blueprint_warning(self):
        bp1 = RawBlueprint(
            var_name="main_bp",
            bp_name="main_bp",
            url_prefix=None,
            url_prefix_dynamic=False,
            location=_loc("a.py", 1),
        )
        bp2 = RawBlueprint(
            var_name="main_bp",
            bp_name="main_bp",
            url_prefix=None,
            url_prefix_dynamic=False,
            location=_loc("b.py", 1),
        )
        nodes = [
            FileRawNodes(
                file="a.py",
                app_instances=[],
                blueprints=[bp1],
                routes=[],
                add_url_rules=[],
                register_blueprints=[],
                before_requests=[],
            ),
            FileRawNodes(
                file="b.py",
                app_instances=[],
                blueprints=[bp2],
                routes=[],
                add_url_rules=[],
                register_blueprints=[],
                before_requests=[],
            ),
        ]
        index = resolve(nodes, project_root=Path("/tmp/proj"))
        warning_text = " ".join(index.warnings)
        assert "main_bp" in warning_text
