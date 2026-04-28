from __future__ import annotations

from typing import Optional

from flask_mcp_lens.extensions.handlers.base import ExtensionHandler
from flask_mcp_lens.models import SourceLoc


class FlaskJWTExtendedHandler(ExtensionHandler):
    package_name = "Flask-JWT-Extended"
    import_name = "flask_jwt_extended"

    def detect_initialization(self, ast_results: object) -> Optional[SourceLoc]:
        return None  # Phase 3 で実装

    def collect_config(self, ast_results: object) -> dict[str, object]:
        return {}  # Phase 3 で実装
