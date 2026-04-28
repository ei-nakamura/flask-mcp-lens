import time

import flask_mcp_lens.tools as tools
from flask_mcp_lens.index import IndexManager
from flask_mcp_lens.tools.list_routes import list_routes


def test_list_routes_performance(factory_nested_bp_root):
    manager = IndexManager(factory_nested_bp_root)
    tools.init(manager)
    start = time.monotonic()
    result = list_routes()
    elapsed = time.monotonic() - start
    assert elapsed < 0.5, f"list_routes took {elapsed:.3f}s, expected < 0.5s"
    assert "data" in result
    assert "routes" in result["data"]
