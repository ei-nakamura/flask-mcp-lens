from __future__ import annotations

import sys
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

if sys.version_info >= (3, 11):
    import tomllib
else:
    try:
        import tomllib
    except ImportError:
        import tomli as tomllib


@dataclass
class AuthConfig:
    extra_decorators: list[str] = field(default_factory=list)
    blacklist_decorators: list[str] = field(default_factory=list)
    extra_functions: list[str] = field(default_factory=list)
    blacklist_functions: list[str] = field(default_factory=list)


@dataclass
class ScanConfig:
    exclude: list[str] = field(default_factory=list)
    exclude_dirs: list[str] = field(default_factory=list)


@dataclass
class Config:
    auth: AuthConfig = field(default_factory=AuthConfig)
    scan: ScanConfig = field(default_factory=ScanConfig)
    hybrid: dict[str, object] = field(default_factory=dict)

    @classmethod
    def load(cls, project_root: Path) -> "Config":
        # .flask-mcp-lens.toml を試みる
        path = project_root / ".flask-mcp-lens.toml"
        # pyproject.toml の [tool.flask-mcp-lens] も試みる
        pyproject_path = project_root / "pyproject.toml"

        data: dict[str, Any] = {}
        if path.exists():
            with open(path, "rb") as f:
                data = tomllib.load(f)
        elif pyproject_path.exists():
            with open(pyproject_path, "rb") as f:
                raw = tomllib.load(f)
            tool = raw.get("tool", {})
            data = tool.get("flask-mcp-lens", {})

        if not data:
            return cls()

        auth_data = data.get("auth", {})
        scan_data = data.get("scan", {})
        hybrid_data = data.get("hybrid", {})

        return cls(
            auth=AuthConfig(
                extra_decorators=list(auth_data.get("extra_decorators", [])),
                blacklist_decorators=list(auth_data.get("blacklist_decorators", [])),
                extra_functions=list(auth_data.get("extra_functions", [])),
                blacklist_functions=list(auth_data.get("blacklist_functions", [])),
            ),
            scan=ScanConfig(
                exclude=list(scan_data.get("exclude", [])),
                exclude_dirs=list(scan_data.get("exclude_dirs", [])),
            ),
            hybrid=dict(hybrid_data) if isinstance(hybrid_data, dict) else {},
        )
