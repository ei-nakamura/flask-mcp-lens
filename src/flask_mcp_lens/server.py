from __future__ import annotations

import argparse
import logging
import sys
from pathlib import Path
from typing import Any

logging.basicConfig(
    stream=sys.stderr,
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(name)s: %(message)s",
)
logger = logging.getLogger(__name__)


def main() -> None:
    parser = argparse.ArgumentParser(
        description="flask-mcp-lens: Flask static analysis MCP server"
    )
    parser.add_argument(
        "--root",
        type=Path,
        default=Path.cwd(),
        help="Flask project root directory (default: cwd)",
    )
    args = parser.parse_args()
    root = args.root.resolve()

    if not root.exists():
        print(f"Error: project root not found: {root}", file=sys.stderr)
        sys.exit(1)

    import flask_mcp_lens.tools as tools_module
    from flask_mcp_lens.index import IndexManager

    manager = IndexManager(root)
    tools_module.init(manager)

    logger.info("flask-mcp-lens starting, root=%s", root)

    from mcp.server.fastmcp import FastMCP

    mcp_server = FastMCP("flask-mcp-lens")

    @mcp_server.tool()
    def find_app_factory() -> dict[str, Any]:
        from flask_mcp_lens.tools.find_app_factory import find_app_factory as _impl
        return _impl()

    @mcp_server.tool()
    def get_app_overview() -> dict[str, Any]:
        from flask_mcp_lens.tools.get_app_overview import get_app_overview as _impl
        return _impl()

    @mcp_server.tool()
    def list_routes(
        blueprint: str = "", url_prefix: str = "", method: str = ""
    ) -> dict[str, Any]:
        from flask_mcp_lens.tools.list_routes import list_routes as _impl
        filter_dict: dict[str, Any] = {}
        if blueprint:
            filter_dict["blueprint"] = blueprint
        if url_prefix:
            filter_dict["url_prefix"] = url_prefix
        if method:
            filter_dict["method"] = method
        return _impl(filter=filter_dict or None)

    @mcp_server.tool()
    def get_route_handler(url: str, method: str = "GET") -> dict[str, Any]:
        from flask_mcp_lens.tools.get_route_handler import get_route_handler as _impl
        return _impl(url=url, method=method)

    @mcp_server.tool()
    def refresh_index() -> dict[str, Any]:
        from flask_mcp_lens.tools.refresh_index import refresh_index as _impl
        return _impl()

    @mcp_server.tool()
    def list_blueprints() -> dict[str, Any]:
        from flask_mcp_lens.tools.list_blueprints import list_blueprints as _impl
        return _impl()

    @mcp_server.tool()
    def list_extensions() -> dict[str, Any]:
        from flask_mcp_lens.tools.list_extensions import list_extensions as _impl
        return _impl()

    @mcp_server.tool()
    def list_auth_strategies() -> dict[str, Any]:
        from flask_mcp_lens.tools.list_auth_strategies import (
            list_auth_strategies as _impl,
        )
        return _impl()

    @mcp_server.tool()
    def find_potentially_unprotected_routes() -> dict[str, Any]:
        from flask_mcp_lens.tools.find_potentially_unprotected_routes import (
            find_potentially_unprotected_routes as _impl,
        )
        return _impl()

    @mcp_server.tool()
    def list_api_endpoints(include: list[str] = []) -> dict[str, Any]:
        from flask_mcp_lens.tools.list_api_endpoints import list_api_endpoints as _impl
        return _impl(include=include or None)

    @mcp_server.tool()
    def get_extension_config(name: str) -> dict[str, Any]:
        from flask_mcp_lens.tools.get_extension_config import (
            get_extension_config as _impl,
        )
        return _impl(name=name)

    mcp_server.run(transport="stdio")


if __name__ == "__main__":
    main()
