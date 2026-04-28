from __future__ import annotations

import re
import sys
from pathlib import Path

if sys.version_info >= (3, 11):
    import tomllib
else:
    try:
        import tomllib
    except ImportError:
        import tomli as tomllib

from flask_mcp_lens.extensions.handlers import KNOWN_EXTENSIONS
from flask_mcp_lens.models import ExtensionInfo


def _normalize(name: str) -> str:
    return re.sub(r"[-_.]+", "-", name).lower()


class ExtensionDetector:
    def detect(
        self, project_root: Path
    ) -> tuple[list[ExtensionInfo], list[dict[str, str]]]:
        """
        Returns (extensions, unsupported_detected).
        unsupported_detected: [{"package": "flask-admin", "reason": "未実装"}, ...]
        """
        declared = self._parse_manifests(project_root)
        extensions: list[ExtensionInfo] = []
        unsupported: list[dict[str, str]] = []

        for pkg_name, sources in declared.items():
            normalized = _normalize(pkg_name)
            if normalized in KNOWN_EXTENSIONS:
                import_name, _handler_cls = KNOWN_EXTENSIONS[normalized]
                extensions.append(ExtensionInfo(
                    name=import_name,
                    package=pkg_name,
                    declared_in=tuple(sources),
                    imported_in=(),
                    initialized_at=None,
                    confidence="medium",
                    config={},
                ))
            elif normalized.startswith("flask-") and normalized != "flask":
                unsupported.append({"package": pkg_name, "reason": "ハンドラ未実装"})

        return extensions, unsupported

    def _parse_manifests(self, project_root: Path) -> dict[str, list[str]]:
        result: dict[str, list[str]] = {}

        pyproject = project_root / "pyproject.toml"
        if pyproject.exists():
            with open(pyproject, "rb") as f:
                data = tomllib.load(f)
            deps: list[str] = []
            deps += list(data.get("project", {}).get("dependencies", []))
            for dep in deps:
                pkg = re.split(r"[>=<!;\[]", dep)[0].strip()
                if pkg:
                    result.setdefault(pkg, []).append("pyproject.toml")

        req = project_root / "requirements.txt"
        if req.exists():
            for line in req.read_text().splitlines():
                line = line.strip()
                if line and not line.startswith("#"):
                    pkg = re.split(r"[>=<!;\[]", line)[0].strip()
                    if pkg:
                        result.setdefault(pkg, []).append("requirements.txt")

        return result
