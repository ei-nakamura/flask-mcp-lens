# flask-mcp-lens

[![Python](https://img.shields.io/badge/python-3.10%2B-blue)](https://www.python.org/)
[![Status](https://img.shields.io/badge/status-Phase%201%20MVP-orange)](docs/design-phase1.md)
[![License](https://img.shields.io/badge/license-MIT-green)](#license)

> 日本語版の README は [README.ja.md](README.ja.md) にあります。

A Model Context Protocol (MCP) server that exposes the structure of a
[Flask](https://flask.palletsprojects.com/) application to LLM agents
(Claude Code, etc.) as a small set of structured tools.

It answers questions that `grep` cannot, such as:

- *"What `before_request` hooks fire when I call `GET /api/v1/users/<id>`?"*
- *"Where is the `app` factory defined and which Blueprints does it register?"*
- *"List every route under `/api/v1` that accepts `POST`."*

Phase 1 ships a **fully static analyzer** — no Flask app is imported or executed.
The analyzer walks the project's Python AST, resolves Blueprints / `register_blueprint`
calls / route decorators, and serves the result through MCP over stdio.

---

## Status

This is the **Phase 1 MVP**. It implements the scope defined in
[docs/design-phase1.md](docs/design-phase1.md):

- 5 MCP tools (see below)
- Static AST analysis with Flask import-alias tracking
- gzip + JSON cache invalidated by file mtimes
- 3 reference fixtures plus unit / integration / perf tests

Authentication detection, extension detection (Flask-Login, Flask-RESTful, …),
unregistered-Blueprint detection, `MethodView`, `.flask-mcp-lens.toml`,
hybrid runtime introspection, and the `watchdog` integration are intentionally
**out of scope for Phase 1**. They are tracked in
[docs/design-phase2.md](docs/design-phase2.md) and later phases.

---

## Features (Phase 1)

| Tool | Purpose |
|------|---------|
| `find_app_factory` | Locate `Flask(...)` instantiations and `create_app`-style factories, with a confidence rating. |
| `get_app_overview` | High-level summary: app factory location, Blueprint count, route count, plus a Markdown summary. |
| `list_routes` | Enumerate every resolved route with optional filtering by `blueprint`, `url_prefix`, or HTTP `method`. |
| `get_route_handler` | Given `(url, method)`, return the matched route plus its execution chain (`before_request` hooks ordered app→blueprint, decorators, view-function source excerpt). |
| `refresh_index` | Invalidate the cache and rebuild the index immediately. |

Every tool returns a JSON envelope:

```jsonc
{
  "tool": "list_routes",
  "version": "1.0",
  "analysis_mode": "static",
  "warnings": [],
  "data": { /* tool-specific payload */ }
}
```

### Supported Flask constructs

- `app = Flask(__name__)` (module-level) and `def create_app(...)` factories
- `Blueprint(...)` definitions — including `from flask import Blueprint as BP` aliases
- Nested Blueprints (parent registers child via `parent_bp.register_blueprint(child_bp)`); up to 2 levels deep
- `@app.route` / `@bp.route` decorators with `methods=` and `endpoint=` kwargs
- `app.add_url_rule(rule, endpoint, view_func, methods=...)`
- `@app.before_request` / `@bp.before_request` decorators **and** `app.before_request(func)` call form
- URL converters: `<name>`, `<int:name>`, `<float:name>`, `<path:name>`, `<uuid:name>`, `<string:name>`

Dynamic values that cannot be resolved statically (e.g. `url_prefix=os.environ.get(...)`,
`add_url_rule(..., view_func=some_dynamic_callable)`) produce entries in the
`warnings` array and are skipped rather than guessed.

---

## Installation

Requires Python **3.10+**.

```bash
# from a clone (recommended while Phase 1 is unpublished)
git clone https://github.com/<your-account>/flask-mcp-lens.git
cd flask-mcp-lens
pip install -e .

# verify the entry point is on PATH
flask-mcp-lens --help
```

The only runtime dependency is [`mcp`](https://pypi.org/project/mcp/) (`>=0.9`).

To install the test extras:

```bash
pip install -e ".[test]"
```

---

## Usage

### As an MCP server

`flask-mcp-lens` speaks MCP over **stdio** — it is started by the agent.

Add it to your MCP client configuration. For Claude Code:

```json
{
  "mcpServers": {
    "flask-mcp-lens": {
      "command": "flask-mcp-lens",
      "args": ["--root", "/absolute/path/to/your/flask/project"]
    }
  }
}
```

If `--root` is omitted, the current working directory is used.

### Logging

Logs are written to **stderr** (stdout is reserved for the MCP protocol).
Set the level via the `FLASK_MCP_LENS_LOG` environment variable (`debug`, `info`, …).

### Excluding extra paths

In addition to the built-in exclusions (`tests/`, `__pycache__/`, `.venv/`,
`build/`, etc.), set `FLASK_MCP_LENS_EXCLUDE` to a comma-separated list of
glob patterns:

```bash
FLASK_MCP_LENS_EXCLUDE="migrations/*,scripts/legacy_*.py" flask-mcp-lens
```

A `.flask-mcp-lens.toml` config file is **not** part of Phase 1 — it is
planned for Phase 2.

### Cache

The first tool call analyzes the project and writes
`.flask-mcp-lens/cache/index-v1.json.gz` under the project root. Subsequent
calls reuse the cache as long as every analyzed file's `mtime` is unchanged
and the file set is identical. Add `.flask-mcp-lens/` to your `.gitignore`.

Call `refresh_index` to force a rebuild.

---

## Example

Given the Phase 1 fixture [`tests/fixtures/factory_nested_bp/`](tests/fixtures/factory_nested_bp/):

```python
# app/__init__.py
def create_app():
    app = Flask(__name__)
    app.register_blueprint(api_v1, url_prefix="/api/v1")
    return app

# app/api/__init__.py    parent Blueprint
api_v1 = Blueprint("api_v1", __name__)
api_v1.register_blueprint(users_api, url_prefix="/users")
api_v1.register_blueprint(posts_api, url_prefix="/posts")

# app/api/users.py       child Blueprint
users_api = Blueprint("users_api", __name__)

@users_api.route("/<int:user_id>", methods=["GET", "DELETE"])
def get_user(user_id): ...
```

`list_routes` returns the fully-joined URL `/api/v1/users/<int:user_id>`
with `methods: ["DELETE", "GET"]`, `blueprint: "users_api"`, and the source
location of the route decorator. `get_route_handler("/api/v1/users/<int:user_id>", "GET")`
adds the resolved `before_request` chain (app-level hooks first, then the
hooks attached to `users_api`) and a 6-line excerpt of the view function.

---

## Project layout

```
flask-mcp-lens/
├── pyproject.toml
├── docs/
│   ├── requirements.md
│   ├── design-phase1.md          ← what this README implements
│   ├── design-phase2.md
│   ├── design-phase3.md
│   └── design-phase4.md
├── src/
│   └── flask_mcp_lens/
│       ├── __main__.py           # python -m flask_mcp_lens
│       ├── server.py             # MCP entrypoint, registers tools
│       ├── tools/
│       │   ├── find_app_factory.py
│       │   ├── get_app_overview.py
│       │   ├── list_routes.py
│       │   ├── get_route_handler.py
│       │   └── refresh_index.py
│       ├── index.py              # IndexManager (cache + lazy build)
│       ├── cache.py              # gzip + JSON, atomic write
│       ├── urlmap.py             # converter-aware URL matcher
│       ├── models.py             # frozen dataclasses
│       └── analyzer/
│           ├── scanner.py        # file enumeration + exclusions
│           ├── ast_visitor.py    # FlaskASTVisitor
│           ├── resolver.py       # raw nodes → RouteIndex
│           └── imports.py        # `from flask import X as Y` alias map
└── tests/
    ├── fixtures/{single_app, factory_one_bp, factory_nested_bp}/
    ├── unit/{test_ast_visitor, test_resolver, test_urlmap, test_cache}.py
    ├── integration/{test_tools_smoke, test_e2e_mcp}.py
    └── perf/test_smoke.py
```

---

## Development

```bash
pip install -e ".[test]"

# run the full test suite
pytest

# only the smoke / golden tests for the three fixtures
pytest tests/integration/test_tools_smoke.py
```

The repo is set up with `ruff` and `mypy --strict` (see `pyproject.toml`):

```bash
ruff check src tests
mypy src
```

---

## Roadmap

| Phase | Highlights |
|-------|-----------|
| **Phase 1** *(this release)* | 5 MCP tools, static AST analyzer, gzip cache, 3 fixtures. |
| Phase 2 | Authentication detection, extension detection (Flask-Login / -RESTful / …), unregistered-Blueprint detection, `MethodView`, `.flask-mcp-lens.toml` config. |
| Phase 3 | Hybrid runtime introspection, `watchdog`-driven incremental analysis. |
| Phase 4 | Plugin mechanism, parallel analysis, HTTP/SSE transport. |
| Phase 5+ | Multi-app monorepos. |

See [`docs/design-phase2.md`](docs/design-phase2.md) onwards for the full plan.

---

## License

MIT.
