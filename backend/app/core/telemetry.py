from __future__ import annotations

import json
import logging
import re
import sys
import time
import uuid
from datetime import datetime, timezone
from typing import Any

from fastapi import Request, Response
from prometheus_client import CONTENT_TYPE_LATEST, Counter, Histogram, generate_latest

REQUESTS = Counter(
    "rag_http_requests_total",
    "HTTP requests handled by the API",
    ("method", "route", "status"),
)
LATENCY = Histogram(
    "rag_http_request_duration_seconds",
    "API request duration in seconds",
    ("method", "route"),
)

_REQUEST_ID = re.compile(r"^[A-Za-z0-9._-]{8,64}$")
_STANDARD_LOG_FIELDS = set(logging.makeLogRecord({}).__dict__)


class SafeJsonFormatter(logging.Formatter):
    """Serialize a small allowlist of structured fields without request content."""

    allowed_extra = {
        "event",
        "request_id",
        "method",
        "path",
        "route",
        "status",
        "duration_ms",
        "error_type",
    }

    def format(self, record: logging.LogRecord) -> str:
        payload: dict[str, Any] = {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
        }
        for key in self.allowed_extra:
            if key not in _STANDARD_LOG_FIELDS and hasattr(record, key):
                payload[key] = getattr(record, key)
        return json.dumps(payload, separators=(",", ":"), default=str)


def configure_logging(level: str) -> None:
    handler = logging.StreamHandler(sys.stdout)
    handler.setFormatter(SafeJsonFormatter())
    root = logging.getLogger()
    root.handlers.clear()
    root.addHandler(handler)
    root.setLevel(level)


def _route_label(request: Request) -> str:
    route = request.scope.get("route")
    path = getattr(route, "path", None)
    return str(path) if path else "unmatched"


async def observe_request(request: Request, call_next: Any) -> Response:
    supplied_request_id = request.headers.get("x-request-id", "")
    request_id = (
        supplied_request_id if _REQUEST_ID.fullmatch(supplied_request_id) else uuid.uuid4().hex
    )
    request.state.request_id = request_id
    started = time.perf_counter()
    status = 500
    try:
        response: Response = await call_next(request)
        status = response.status_code
        return response
    finally:
        duration = time.perf_counter() - started
        route = _route_label(request)
        REQUESTS.labels(request.method, route, str(status)).inc()
        LATENCY.labels(request.method, route).observe(duration)
        logging.getLogger("rag.http").info(
            "request_completed",
            extra={
                "event": "request_completed",
                "request_id": request_id,
                "method": request.method,
                "path": request.url.path,
                "route": route,
                "status": status,
                "duration_ms": round(duration * 1000, 2),
            },
        )


def metrics_response() -> Response:
    return Response(content=generate_latest(), media_type=CONTENT_TYPE_LATEST)
