from __future__ import annotations

import fnmatch
import os
from pathlib import Path

_EXCLUDED_DIRS = frozenset({
    ".git", ".venv", "venv", "env", ".env", "__pycache__", "node_modules",
    ".tox", ".mypy_cache", ".pytest_cache", ".flask-mcp-lens", "build", "dist",
    "tests", "test",
})
_EXCLUDED_FILE_PATTERNS = ("test_*.py", "*_test.py", "conftest.py")
_MAX_FILE_SIZE = 1024 * 1024  # 1 MB


def scan_files(
    root: Path,
    extra_excludes: list[str] | None = None,
) -> tuple[list[tuple[Path, float]], list[str]]:
    """Enumerate .py files under root, applying exclusion rules.

    Returns ([(path, mtime), ...], warnings).
    """
    if extra_excludes is None:
        extra_excludes = []

    env_val = os.environ.get("FLASK_MCP_LENS_EXCLUDE", "")
    env_excludes = (
        [p.strip() for p in env_val.split(",") if p.strip()] if env_val else []
    )
    all_extra = extra_excludes + env_excludes

    files: list[tuple[Path, float]] = []
    warnings: list[str] = []

    for dirpath_str, dirnames, filenames in os.walk(str(root)):
        dirpath = Path(dirpath_str)

        dirnames[:] = [
            d for d in dirnames
            if d not in _EXCLUDED_DIRS and not d.startswith(".")
        ]

        for filename in filenames:
            if not filename.endswith(".py"):
                continue

            filepath = dirpath / filename
            try:
                rel = filepath.relative_to(root)
            except ValueError:
                continue
            rel_str = rel.as_posix()

            if any(fnmatch.fnmatch(filename, pat) for pat in _EXCLUDED_FILE_PATTERNS):
                continue

            if all_extra and any(
                fnmatch.fnmatch(rel_str, pat) or fnmatch.fnmatch(filename, pat)
                for pat in all_extra
            ):
                continue

            try:
                st = filepath.stat()
            except OSError:
                continue

            if st.st_size > _MAX_FILE_SIZE:
                warnings.append(
                    f"{rel_str}: ファイルサイズ超過 ({st.st_size} bytes)、スキップ"
                )
                continue

            try:
                filepath.read_text(encoding="utf-8")
            except (UnicodeDecodeError, OSError):
                warnings.append(f"{rel_str}: UTF-8 読み込み失敗、スキップ")
                continue

            files.append((filepath, st.st_mtime))

    return files, warnings
