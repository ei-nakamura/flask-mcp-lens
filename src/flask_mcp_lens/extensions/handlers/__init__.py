from __future__ import annotations

from flask_mcp_lens.extensions.handlers.flask_jwt_extended import (
    FlaskJWTExtendedHandler,
)
from flask_mcp_lens.extensions.handlers.flask_login import FlaskLoginHandler

KNOWN_EXTENSIONS: dict[str, tuple[str, type]] = {
    "flask-login":        ("flask_login", FlaskLoginHandler),
    "flask-jwt-extended": ("flask_jwt_extended", FlaskJWTExtendedHandler),
}

__all__ = ["KNOWN_EXTENSIONS", "FlaskLoginHandler", "FlaskJWTExtendedHandler"]
