import gzip

from flask_mcp_lens.cache import load, save
from flask_mcp_lens.models import RouteIndex


def make_simple_index(project_root: str = "/tmp/test") -> RouteIndex:
    return RouteIndex(
        project_root=project_root,
        analyzed_at=1_000_000.0,
        file_mtimes={"app.py": 1_000_000.0},
        app_factories=(),
        selected_factory=0,
        blueprints=(),
        routes=(),
        before_request_hooks=(),
        warnings=(),
    )


class TestSaveLoad:
    def test_round_trip(self, tmp_path):
        cache_path = tmp_path / "index.json.gz"
        original = make_simple_index(str(tmp_path))
        save(original, cache_path)
        loaded = load(cache_path)
        assert loaded is not None
        assert loaded.project_root == original.project_root
        assert loaded.analyzed_at == original.analyzed_at
        assert loaded.file_mtimes == original.file_mtimes
        assert loaded.routes == original.routes
        assert loaded.blueprints == original.blueprints
        assert loaded.warnings == original.warnings

    def test_load_nonexistent_returns_none(self, tmp_path):
        missing = tmp_path / "does_not_exist.json.gz"
        assert load(missing) is None

    def test_load_corrupted_gzip_returns_none(self, tmp_path):
        bad_file = tmp_path / "corrupt.json.gz"
        bad_file.write_bytes(b"this is not valid gzip data")
        assert load(bad_file) is None

    def test_load_valid_gzip_invalid_json_returns_none(self, tmp_path):
        bad_file = tmp_path / "bad_json.json.gz"
        with gzip.open(bad_file, "wb") as f:
            f.write(b"not valid json {{{{")
        assert load(bad_file) is None

    def test_atomic_write_no_tmp_left(self, tmp_path):
        cache_path = tmp_path / "index.json.gz"
        index = make_simple_index(str(tmp_path))
        save(index, cache_path)
        tmp_files = list(tmp_path.glob("*.tmp"))
        assert tmp_files == [], f"Unexpected tmp files: {tmp_files}"
        assert cache_path.exists()
