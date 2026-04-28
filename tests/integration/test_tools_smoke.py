import jsonschema
import pytest

import flask_mcp_lens.tools as tools
from flask_mcp_lens.index import IndexManager
from flask_mcp_lens.tools.find_app_factory import find_app_factory
from flask_mcp_lens.tools.find_potentially_unprotected_routes import (
    find_potentially_unprotected_routes,
)
from flask_mcp_lens.tools.get_app_overview import get_app_overview
from flask_mcp_lens.tools.get_extension_config import get_extension_config
from flask_mcp_lens.tools.list_api_endpoints import list_api_endpoints
from flask_mcp_lens.tools.list_auth_strategies import list_auth_strategies
from flask_mcp_lens.tools.list_blueprints import list_blueprints
from flask_mcp_lens.tools.list_extensions import list_extensions
from flask_mcp_lens.tools.list_routes import list_routes

ENVELOPE_SCHEMA = {
    "type": "object",
    "required": ["tool", "version", "analysis_mode", "warnings", "data"],
    "properties": {
        "tool": {"type": "string"},
        "version": {"type": "string"},
        "analysis_mode": {"type": "string"},
        "warnings": {"type": "array", "items": {"type": "string"}},
        "data": {"type": "object"},
    },
    "additionalProperties": False,
}

LIST_ROUTES_DATA_SCHEMA = {
    "type": "object",
    "required": ["routes", "total", "filtered_from"],
    "properties": {
        "routes": {
            "type": "array",
            "items": {
                "type": "object",
                "required": [
                    "url", "methods", "endpoint",
                    "view_function", "blueprint",
                    "definition", "decorators",
                ],
                "properties": {
                    "url": {"type": "string"},
                    "methods": {"type": "array", "items": {"type": "string"}},
                    "endpoint": {"type": "string"},
                    "view_function": {"type": "string"},
                    "blueprint": {"type": ["string", "null"]},
                    "definition": {
                        "type": "object",
                        "required": ["file", "line"],
                        "properties": {
                            "file": {"type": "string"},
                            "line": {"type": "integer"},
                        },
                    },
                    "decorators": {"type": "array"},
                    "auth_signal": {},
                },
            },
        },
        "total": {"type": "integer"},
        "filtered_from": {"type": "integer"},
    },
}

GET_APP_OVERVIEW_DATA_SCHEMA = {
    "type": "object",
    "required": [
        "blueprint_count",
        "route_count",
        "extensions_detected",
        "auth_strategies_summary",
    ],
    "properties": {
        "app_factory": {
            "anyOf": [
                {
                    "type": "object",
                    "required": ["file", "line", "kind", "name"],
                    "properties": {
                        "file": {"type": "string"},
                        "line": {"type": "integer"},
                        "kind": {"type": "string"},
                        "name": {"type": "string"},
                    },
                },
                {"type": "null"},
            ]
        },
        "blueprint_count": {"type": "integer"},
        "route_count": {"type": "integer"},
        "extensions_detected": {"type": "array"},
        "auth_strategies_summary": {},
    },
}


FIXTURE_ROOTS = [
    "single_app_root", "factory_one_bp_root", "factory_nested_bp_root", "full_app_root"
]


@pytest.mark.parametrize("fixture_name", FIXTURE_ROOTS)
def test_list_routes_envelope_schema(fixture_name, request):
    root = request.getfixturevalue(fixture_name)
    manager = IndexManager(root)
    tools.init(manager)
    result = list_routes()
    jsonschema.validate(result, ENVELOPE_SCHEMA)
    jsonschema.validate(result["data"], LIST_ROUTES_DATA_SCHEMA)


@pytest.mark.parametrize("fixture_name", FIXTURE_ROOTS)
def test_get_app_overview_envelope_schema(fixture_name, request):
    root = request.getfixturevalue(fixture_name)
    manager = IndexManager(root)
    tools.init(manager)
    result = get_app_overview()
    jsonschema.validate(result, ENVELOPE_SCHEMA)
    jsonschema.validate(result["data"], GET_APP_OVERVIEW_DATA_SCHEMA)


@pytest.mark.parametrize("fixture_name", FIXTURE_ROOTS)
def test_find_app_factory_envelope_schema(fixture_name, request):
    root = request.getfixturevalue(fixture_name)
    manager = IndexManager(root)
    tools.init(manager)
    result = find_app_factory()
    jsonschema.validate(result, ENVELOPE_SCHEMA)
    assert "candidates" in result["data"]
    assert isinstance(result["data"]["candidates"], list)


@pytest.mark.parametrize("fixture_name", FIXTURE_ROOTS)
def test_list_routes_tool_field(fixture_name, request):
    root = request.getfixturevalue(fixture_name)
    manager = IndexManager(root)
    tools.init(manager)
    result = list_routes()
    assert result["tool"] == "list_routes"
    assert result["analysis_mode"] == "static"


@pytest.mark.parametrize("fixture_name", FIXTURE_ROOTS)
def test_get_app_overview_tool_field(fixture_name, request):
    root = request.getfixturevalue(fixture_name)
    manager = IndexManager(root)
    tools.init(manager)
    result = get_app_overview()
    assert result["tool"] == "get_app_overview"
    assert result["analysis_mode"] == "static"


@pytest.mark.parametrize("fixture_name", ["full_app_root"])
def test_list_blueprints_envelope_schema(fixture_name, request):
    root = request.getfixturevalue(fixture_name)
    manager = IndexManager(root)
    tools.init(manager)
    result = list_blueprints()
    jsonschema.validate(result, ENVELOPE_SCHEMA)
    assert "blueprints" in result["data"]
    assert "unregistered_count" in result["data"]


@pytest.mark.parametrize("fixture_name", ["full_app_root"])
def test_list_extensions_envelope_schema(fixture_name, request):
    root = request.getfixturevalue(fixture_name)
    manager = IndexManager(root)
    tools.init(manager)
    result = list_extensions()
    jsonschema.validate(result, ENVELOPE_SCHEMA)
    assert "extensions" in result["data"]


@pytest.mark.parametrize("fixture_name", ["full_app_root"])
def test_list_auth_strategies_envelope_schema(fixture_name, request):
    root = request.getfixturevalue(fixture_name)
    manager = IndexManager(root)
    tools.init(manager)
    result = list_auth_strategies()
    jsonschema.validate(result, ENVELOPE_SCHEMA)
    assert "strategies" in result["data"]


@pytest.mark.parametrize("fixture_name", ["full_app_root"])
def test_find_potentially_unprotected_routes_envelope_schema(fixture_name, request):
    root = request.getfixturevalue(fixture_name)
    manager = IndexManager(root)
    tools.init(manager)
    result = find_potentially_unprotected_routes()
    jsonschema.validate(result, ENVELOPE_SCHEMA)
    assert "definitely_unprotected" in result["data"]
    assert "summary" in result["data"]


@pytest.mark.parametrize("fixture_name", ["full_app_root"])
def test_list_api_endpoints_envelope_schema(fixture_name, request):
    root = request.getfixturevalue(fixture_name)
    manager = IndexManager(root)
    tools.init(manager)
    result = list_api_endpoints()
    jsonschema.validate(result, ENVELOPE_SCHEMA)
    assert "endpoints" in result["data"]


@pytest.mark.parametrize("fixture_name", ["full_app_root"])
def test_get_extension_config_unknown(fixture_name, request):
    root = request.getfixturevalue(fixture_name)
    manager = IndexManager(root)
    tools.init(manager)
    result = get_extension_config("unknown_ext")
    jsonschema.validate(result, ENVELOPE_SCHEMA)
    assert "error" in result["data"]
