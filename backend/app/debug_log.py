from __future__ import annotations

import json
import time
from pathlib import Path
from typing import Any


SESSION_ID = "8e589e"
LOG_PATH = Path(__file__).resolve().parents[2] / "debug-8e589e.log"


def debug_log(
    *,
    hypothesisId: str,
    message: str,
    data: dict[str, Any] | None = None,
    runId: str = "initial",
    location: str = "backend/app",
) -> None:
    """Append a single NDJSON debug event.

    Keep this tiny and best-effort: logging must never break the API.
    """

    payload: dict[str, Any] = {
        "sessionId": SESSION_ID,
        "runId": runId,
        "hypothesisId": hypothesisId,
        "location": location,
        "message": message,
        "data": data or {},
        "timestamp": int(time.time() * 1000),
    }
    try:
        LOG_PATH.parent.mkdir(parents=True, exist_ok=True)
        with LOG_PATH.open("a", encoding="utf-8") as f:
            f.write(json.dumps(payload, default=str) + "\n")
    except Exception:
        # Never fail production request paths because debugging IO failed.
        pass

