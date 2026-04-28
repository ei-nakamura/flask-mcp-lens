
from flask_mcp_lens.config import Config


def test_default_config(tmp_path):
    cfg = Config.load(tmp_path)
    assert cfg.auth.extra_decorators == []
    assert cfg.auth.blacklist_decorators == []
    assert cfg.scan.exclude == []


def test_load_from_toml(tmp_path):
    toml_file = tmp_path / ".flask-mcp-lens.toml"
    toml_file.write_bytes(
        b'[auth]\nextra_decorators = ["require_admin"]\n'
        b'blacklist_decorators = ["debug_view"]\n'
        b'[scan]\nexclude = ["legacy/**"]\n'
    )
    cfg = Config.load(tmp_path)
    assert "require_admin" in cfg.auth.extra_decorators
    assert "debug_view" in cfg.auth.blacklist_decorators
    assert "legacy/**" in cfg.scan.exclude


def test_load_from_pyproject(tmp_path):
    pyproject = tmp_path / "pyproject.toml"
    pyproject.write_bytes(
        b'[tool.flask-mcp-lens]\n'
        b'[tool.flask-mcp-lens.auth]\nextra_decorators = ["my_auth"]\n'
    )
    cfg = Config.load(tmp_path)
    assert "my_auth" in cfg.auth.extra_decorators
