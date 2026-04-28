"""
MCP stdio プロトコル実動作テスト
flask-mcp-lens を subprocess で起動し、MCP JSON-RPC 経由でツールを呼び出す。
"""
import json
import subprocess
import sys
import time
from pathlib import Path
from typing import Generator

import pytest

FIXTURES_DIR = Path(__file__).parent.parent / "fixtures"
TIMEOUT = 10  # seconds

def send_request(
    proc: subprocess.Popen,
    method: str,
    params: dict = None,
    req_id: int = 1,
) -> dict:
    """MCP JSON-RPC リクエストを送信して応答を受け取る。"""
    request = {
        "jsonrpc": "2.0",
        "id": req_id,
        "method": method,
        "params": params or {},
    }
    msg = json.dumps(request) + "\n"
    proc.stdin.write(msg.encode())
    proc.stdin.flush()

    # 応答ラインを読む
    deadline = time.monotonic() + TIMEOUT
    while time.monotonic() < deadline:
        line = proc.stdout.readline()
        if line:
            return json.loads(line.decode())
    raise TimeoutError(f"No response for {method} within {TIMEOUT}s")

@pytest.fixture
def mcp_server(tmp_path) -> Generator[subprocess.Popen, None, None]:
    """single_app fixture を対象に MCP サーバを起動する。"""
    fixture_root = FIXTURES_DIR / "single_app"
    proc = subprocess.Popen(
        [sys.executable, "-m", "flask_mcp_lens", "--root", str(fixture_root)],
        stdin=subprocess.PIPE,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
    )
    # MCP initialize
    send_request(proc, "initialize", {
        "protocolVersion": "2024-11-05",
        "capabilities": {},
        "clientInfo": {"name": "test-client", "version": "0.1"},
    })
    yield proc
    proc.terminate()
    proc.wait(timeout=5)

@pytest.fixture
def mcp_server_factory(tmp_path) -> Generator[subprocess.Popen, None, None]:
    """factory_one_bp fixture を対象に MCP サーバを起動する。"""
    fixture_root = FIXTURES_DIR / "factory_one_bp"
    proc = subprocess.Popen(
        [sys.executable, "-m", "flask_mcp_lens", "--root", str(fixture_root)],
        stdin=subprocess.PIPE,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
    )
    send_request(proc, "initialize", {
        "protocolVersion": "2024-11-05",
        "capabilities": {},
        "clientInfo": {"name": "test-client", "version": "0.1"},
    })
    yield proc
    proc.terminate()
    proc.wait(timeout=5)

@pytest.fixture
def mcp_server_nested(tmp_path) -> Generator[subprocess.Popen, None, None]:
    """factory_nested_bp fixture を対象に MCP サーバを起動する。"""
    fixture_root = FIXTURES_DIR / "factory_nested_bp"
    proc = subprocess.Popen(
        [sys.executable, "-m", "flask_mcp_lens", "--root", str(fixture_root)],
        stdin=subprocess.PIPE,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
    )
    send_request(proc, "initialize", {
        "protocolVersion": "2024-11-05",
        "capabilities": {},
        "clientInfo": {"name": "test-client", "version": "0.1"},
    })
    yield proc
    proc.terminate()
    proc.wait(timeout=5)

EXPECTED_TOOLS = {
    "find_app_factory",
    "get_app_overview",
    "list_routes",
    "get_route_handler",
    "refresh_index",
    "list_blueprints",
    "list_extensions",
    "list_auth_strategies",
    "find_potentially_unprotected_routes",
    "list_api_endpoints",
    "get_extension_config",
}

def _assert_envelope(result: dict, tool_name: str) -> dict:
    """共通エンベロープ構造を検証してdata部を返す。"""
    assert result.get("tool") == tool_name
    assert result.get("version") == "1.0"
    assert result.get("analysis_mode") == "static"
    assert "warnings" in result
    assert isinstance(result["warnings"], list)
    assert "data" in result
    return result["data"]

def _call_tool(
    proc: subprocess.Popen,
    tool_name: str,
    arguments: dict = None,
    req_id: int = 1,
) -> dict:
    """tools/call で MCP ツールを呼び出し結果を JSON パースして返す。"""
    resp = send_request(proc, "tools/call", {
        "name": tool_name,
        "arguments": arguments or {},
    }, req_id=req_id)
    assert "result" in resp or "error" not in resp, f"Tool call error: {resp}"
    content = resp["result"]["content"]
    # content は [{type: text, text: "...JSON..."}] 形式
    assert len(content) > 0
    assert content[0]["type"] == "text"
    return json.loads(content[0]["text"])

# =========================================
# テスト 1: tools/list で 5 ツール登録確認
# =========================================

def test_tools_list_single_app(mcp_server):
    resp = send_request(mcp_server, "tools/list", {})
    tools = {t["name"] for t in resp["result"]["tools"]}
    assert EXPECTED_TOOLS.issubset(tools), f"Missing tools: {EXPECTED_TOOLS - tools}"

def test_tools_list_factory_one_bp(mcp_server_factory):
    resp = send_request(mcp_server_factory, "tools/list", {})
    tools = {t["name"] for t in resp["result"]["tools"]}
    assert EXPECTED_TOOLS.issubset(tools)

def test_tools_list_factory_nested_bp(mcp_server_nested):
    resp = send_request(mcp_server_nested, "tools/list", {})
    tools = {t["name"] for t in resp["result"]["tools"]}
    assert EXPECTED_TOOLS.issubset(tools)

# =========================================
# テスト 2: find_app_factory — 3 fixture
# =========================================

def test_find_app_factory_single_app(mcp_server):
    result = _call_tool(mcp_server, "find_app_factory", req_id=2)
    data = _assert_envelope(result, "find_app_factory")
    assert "candidates" in data
    assert len(data["candidates"]) >= 1
    assert data["candidates"][0]["kind"] == "module_level_app"

def test_find_app_factory_factory_one_bp(mcp_server_factory):
    result = _call_tool(mcp_server_factory, "find_app_factory", req_id=2)
    data = _assert_envelope(result, "find_app_factory")
    assert any(c["kind"] == "factory_function" for c in data["candidates"])

def test_find_app_factory_nested_bp(mcp_server_nested):
    result = _call_tool(mcp_server_nested, "find_app_factory", req_id=2)
    data = _assert_envelope(result, "find_app_factory")
    assert len(data["candidates"]) >= 1

# =========================================
# テスト 3: get_app_overview — 3 fixture
# =========================================

def test_get_app_overview_single_app(mcp_server):
    result = _call_tool(mcp_server, "get_app_overview", req_id=3)
    data = _assert_envelope(result, "get_app_overview")
    assert "route_count" in data
    assert data["route_count"] == 3
    assert data["blueprint_count"] == 0
    assert data["extensions_detected"] == []
    summary = data["auth_strategies_summary"]
    assert summary is None or isinstance(summary, dict)

def test_get_app_overview_factory_one_bp(mcp_server_factory):
    result = _call_tool(mcp_server_factory, "get_app_overview", req_id=3)
    data = _assert_envelope(result, "get_app_overview")
    assert data["blueprint_count"] >= 1
    assert data["route_count"] == 5

def test_get_app_overview_nested_bp(mcp_server_nested):
    result = _call_tool(mcp_server_nested, "get_app_overview", req_id=3)
    data = _assert_envelope(result, "get_app_overview")
    assert data["blueprint_count"] >= 2
    assert data["route_count"] >= 4

# =========================================
# テスト 4: list_routes — 3 fixture
# =========================================

def test_list_routes_single_app(mcp_server):
    result = _call_tool(mcp_server, "list_routes", req_id=4)
    data = _assert_envelope(result, "list_routes")
    assert "routes" in data
    assert data["total"] == 3
    urls = {r["url"] for r in data["routes"]}
    assert "/" in urls
    assert "/users" in urls
    assert "/users/<int:user_id>" in urls

def test_list_routes_factory_one_bp(mcp_server_factory):
    result = _call_tool(mcp_server_factory, "list_routes", req_id=4)
    data = _assert_envelope(result, "list_routes")
    assert data["total"] == 5
    assert all(r["url"].startswith("/main") for r in data["routes"])

def test_list_routes_nested_bp(mcp_server_nested):
    result = _call_tool(mcp_server_nested, "list_routes", req_id=4)
    data = _assert_envelope(result, "list_routes")
    assert data["total"] >= 4
    urls = {r["url"] for r in data["routes"]}
    assert "/api/v1/users/" in urls or any("/api/v1/users" in u for u in urls)

# =========================================
# テスト 5: get_route_handler — 3 fixture
# =========================================

def test_get_route_handler_single_app(mcp_server):
    result = _call_tool(
        mcp_server, "get_route_handler", {"url": "/", "method": "GET"}, req_id=5
    )
    data = _assert_envelope(result, "get_route_handler")
    assert "execution_chain" in data or "error" in data

def test_get_route_handler_not_found(mcp_server):
    result = _call_tool(
        mcp_server,
        "get_route_handler",
        {"url": "/nonexistent", "method": "GET"},
        req_id=6,
    )
    # エラーパスの場合は suggestions が返る
    assert "data" in result

def test_get_route_handler_nested_bp(mcp_server_nested):
    result = _call_tool(mcp_server_nested, "get_route_handler",
                        {"url": "/api/v1/users/", "method": "GET"}, req_id=5)
    data = _assert_envelope(result, "get_route_handler")
    assert "execution_chain" in data or "error" in data

# =========================================
# テスト 6: refresh_index — 3 fixture
# =========================================

def test_refresh_index_single_app(mcp_server):
    result = _call_tool(mcp_server, "refresh_index", req_id=7)
    data = _assert_envelope(result, "refresh_index")
    assert data["refreshed"] is True
    assert "duration_ms" in data
    assert isinstance(data["duration_ms"], int)
    assert data["route_count"] == 3

def test_refresh_index_factory_one_bp(mcp_server_factory):
    result = _call_tool(mcp_server_factory, "refresh_index", req_id=7)
    data = _assert_envelope(result, "refresh_index")
    assert data["refreshed"] is True
    assert data["route_count"] == 5

def test_refresh_index_nested_bp(mcp_server_nested):
    result = _call_tool(mcp_server_nested, "refresh_index", req_id=7)
    data = _assert_envelope(result, "refresh_index")
    assert data["refreshed"] is True
    assert data["route_count"] >= 4

# =========================================
# テスト 7: list_blueprints
# =========================================

def test_list_blueprints_single_app(mcp_server):
    result = _call_tool(mcp_server, "list_blueprints", req_id=10)
    data = _assert_envelope(result, "list_blueprints")
    assert "blueprints" in data
    assert "unregistered_count" in data
    assert isinstance(data["blueprints"], list)

def test_list_blueprints_factory_one_bp(mcp_server_factory):
    result = _call_tool(mcp_server_factory, "list_blueprints", req_id=10)
    data = _assert_envelope(result, "list_blueprints")
    assert "blueprints" in data
    assert len(data["blueprints"]) >= 1

# =========================================
# テスト 8: list_extensions
# =========================================

def test_list_extensions_single_app(mcp_server):
    result = _call_tool(mcp_server, "list_extensions", req_id=11)
    data = _assert_envelope(result, "list_extensions")
    assert "extensions" in data
    assert isinstance(data["extensions"], list)

# =========================================
# テスト 9: list_auth_strategies
# =========================================

def test_list_auth_strategies_single_app(mcp_server):
    result = _call_tool(mcp_server, "list_auth_strategies", req_id=12)
    data = _assert_envelope(result, "list_auth_strategies")
    assert "strategies" in data
    assert isinstance(data["strategies"], list)

# =========================================
# テスト 10: find_potentially_unprotected_routes
# =========================================

def test_find_potentially_unprotected_routes_single_app(mcp_server):
    result = _call_tool(mcp_server, "find_potentially_unprotected_routes", req_id=13)
    data = _assert_envelope(result, "find_potentially_unprotected_routes")
    assert "definitely_unprotected" in data
    assert "likely_unprotected" in data
    assert "summary" in data

# =========================================
# テスト 11: list_api_endpoints
# =========================================

def test_list_api_endpoints_single_app(mcp_server):
    result = _call_tool(mcp_server, "list_api_endpoints", req_id=14)
    data = _assert_envelope(result, "list_api_endpoints")
    assert "endpoints" in data
    assert isinstance(data["endpoints"], list)

# =========================================
# テスト 12: get_extension_config
# =========================================

def test_get_extension_config_unknown(mcp_server):
    result = _call_tool(
        mcp_server, "get_extension_config", {"name": "unknown_ext"}, req_id=15
    )
    data = _assert_envelope(result, "get_extension_config")
    assert "error" in data
