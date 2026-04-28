from __future__ import annotations

import time
from typing import Any

from flask_mcp_lens.tools import envelope, get_manager


def refresh_index() -> dict[str, Any]:
    start = time.monotonic()
    index = get_manager().invalidate()
    duration_ms = int((time.monotonic() - start) * 1000)
    return envelope(
        "refresh_index",
        {
            "refreshed": True,
            "duration_ms": duration_ms,
            "route_count": len(index.routes),
        },
        warnings=list(index.warnings),
    )
