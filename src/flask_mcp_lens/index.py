from __future__ import annotations

import threading
import time
from pathlib import Path
from typing import Optional

from flask_mcp_lens import cache as cache_module
from flask_mcp_lens.analyzer import resolver, scanner
from flask_mcp_lens.analyzer.ast_visitor import visit_file
from flask_mcp_lens.models import RouteIndex


class IndexManager:
    def __init__(self, project_root: Path) -> None:
        self._project_root = project_root
        self._cache_path = (
            project_root / ".flask-mcp-lens" / "cache" / "index-v1.json.gz"
        )
        self._index: Optional[RouteIndex] = None
        self._lock = threading.Lock()

    def get(self) -> RouteIndex:
        with self._lock:
            if self._index is not None and self._is_valid(self._index):
                return self._index
            self._index = self._build()
            return self._index

    def invalidate(self) -> RouteIndex:
        with self._lock:
            self._index = None
            index = self._build()
            self._index = index
            return index

    def _is_valid(self, index: RouteIndex) -> bool:
        if not self._cache_path.exists():
            return False
        file_pairs, _warnings = scanner.scan_files(self._project_root)
        current_files = {
            path.relative_to(self._project_root).as_posix(): mtime
            for path, mtime in file_pairs
        }
        if set(current_files.keys()) != set(index.file_mtimes.keys()):
            return False
        for rel, mtime in current_files.items():
            if index.file_mtimes.get(rel) != mtime:
                return False
        return True

    def _build(self) -> RouteIndex:
        cached = cache_module.load(self._cache_path)
        if cached is not None and self._cache_is_still_valid(cached):
            return cached

        file_pairs, scan_warnings = scanner.scan_files(self._project_root)
        file_mtimes: dict[str, float] = {
            path.relative_to(self._project_root).as_posix(): mtime
            for path, mtime in file_pairs
        }

        all_raw_nodes = []
        visit_warnings: list[str] = []
        for path, _mtime in file_pairs:
            result = visit_file(path, self._project_root)
            if result is None:
                rel = path.relative_to(self._project_root).as_posix()
                visit_warnings.append(f"{rel}: 構文エラーまたは読み込み失敗")
            else:
                all_raw_nodes.append(result)

        index = resolver.resolve(
            all_raw_nodes,
            self._project_root,
            file_mtimes=file_mtimes,
        )

        extra_warnings = scan_warnings + visit_warnings
        if extra_warnings:
            merged = tuple(sorted(set(index.warnings) | set(extra_warnings)))
            index = RouteIndex(
                schema_version=index.schema_version,
                project_root=index.project_root,
                analyzed_at=time.time(),
                file_mtimes=file_mtimes,
                app_factories=index.app_factories,
                selected_factory=index.selected_factory,
                blueprints=index.blueprints,
                routes=index.routes,
                before_request_hooks=index.before_request_hooks,
                warnings=merged,
            )
        else:
            index = RouteIndex(
                schema_version=index.schema_version,
                project_root=index.project_root,
                analyzed_at=time.time(),
                file_mtimes=file_mtimes,
                app_factories=index.app_factories,
                selected_factory=index.selected_factory,
                blueprints=index.blueprints,
                routes=index.routes,
                before_request_hooks=index.before_request_hooks,
                warnings=index.warnings,
            )

        try:
            cache_module.save(index, self._cache_path)
        except Exception as exc:
            warn = f"キャッシュ書き込み失敗、起動毎に再解析: {exc}"
            index = RouteIndex(
                schema_version=index.schema_version,
                project_root=index.project_root,
                analyzed_at=index.analyzed_at,
                file_mtimes=index.file_mtimes,
                app_factories=index.app_factories,
                selected_factory=index.selected_factory,
                blueprints=index.blueprints,
                routes=index.routes,
                before_request_hooks=index.before_request_hooks,
                warnings=tuple(sorted(set(index.warnings) | {warn})),
            )

        return index

    def _cache_is_still_valid(self, cached: RouteIndex) -> bool:
        file_pairs, _warnings = scanner.scan_files(self._project_root)
        current_files = {
            path.relative_to(self._project_root).as_posix(): mtime
            for path, mtime in file_pairs
        }
        if set(current_files.keys()) != set(cached.file_mtimes.keys()):
            return False
        for rel, mtime in current_files.items():
            if cached.file_mtimes.get(rel) != mtime:
                return False
        return True
