from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Optional

from flask_mcp_lens.models import SourceLoc


class ExtensionHandler(ABC):
    package_name: str
    import_name: str

    @abstractmethod
    def detect_initialization(self, ast_results: object) -> Optional[SourceLoc]:
        """LoginManager() / JWTManager() 等の初期化位置を返す。"""

    @abstractmethod
    def collect_config(self, ast_results: object) -> dict[str, object]:
        """各種 setattr / decorator 等から設定を集める。"""
