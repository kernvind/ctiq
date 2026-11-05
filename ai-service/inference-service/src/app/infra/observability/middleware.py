"""ASGI middleware: request id, access log, and HTTP metrics.

Written as a plain ASGI middleware (not Starlette's BaseHTTPMiddleware) so it adds no extra
task/stream layer per request and keeps ContextVars intact for everything downstream.

PHI/PII note: the access log records the method, the route template and the *path* — never the
query string, because `/api/v1/search/trials?q=` carries free-text patient queries.
"""
import logging
import re
import time
import uuid

from starlette.datastructures import MutableHeaders
from starlette.types import ASGIApp, Message, Receive, Scope, Send

from src.app.core.request_context import request_id_var
from src.app.infra.observability.metrics import HTTP_IN_PROGRESS, HTTP_LATENCY, HTTP_REQUESTS

logger = logging.getLogger("app.access")

REQUEST_ID_HEADER = "X-Request-ID"
# Health probes and the scrape endpoint fire every few seconds; they'd drown real traffic.
_SKIP_PATHS = frozenset({"/", "/metrics"})
# Accept a caller-supplied id (api-core can forward one) only if it is short and boring, so
# it can't be used to inject odd characters into logs.
_SAFE_REQUEST_ID = re.compile(r"^[A-Za-z0-9._-]{1,64}$")


def _resolve_request_id(scope: Scope) -> str:
    for name, value in scope["headers"]:
        if name == b"x-request-id":
            candidate = value.decode("latin-1")
            if _SAFE_REQUEST_ID.match(candidate):
                return candidate
            break
    return uuid.uuid4().hex


class ObservabilityMiddleware:
    def __init__(self, app: ASGIApp) -> None:
        self.app = app

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] != "http" or scope["path"] in _SKIP_PATHS:
            await self.app(scope, receive, send)
            return

        request_id = _resolve_request_id(scope)
        token = request_id_var.set(request_id)
        method = scope["method"]
        status_code = 500  # stays 500 if the app raises before sending a response
        started = time.perf_counter()
        HTTP_IN_PROGRESS.inc()

        async def send_with_request_id(message: Message) -> None:
            nonlocal status_code
            if message["type"] == "http.response.start":
                status_code = message["status"]
                MutableHeaders(scope=message)[REQUEST_ID_HEADER] = request_id
            await send(message)

        try:
            await self.app(scope, receive, send_with_request_id)
        finally:
            duration = time.perf_counter() - started
            # The router stores the matched route on the scope. Using its *template*
            # ("/api/v1/search/trials/{nct_id}") keeps label cardinality bounded; unmatched
            # paths (404 scans, typos) all collapse into one label.
            route = getattr(scope.get("route"), "path", None) or "unmatched"
            HTTP_IN_PROGRESS.dec()
            HTTP_REQUESTS.labels(method, route, str(status_code)).inc()
            HTTP_LATENCY.labels(method, route).observe(duration)
            level = (
                logging.ERROR if status_code >= 500
                else logging.WARNING if status_code >= 400
                else logging.INFO
            )
            logger.log(
                level,
                "request completed",
                extra={
                    "http_method": method,
                    "http_path": scope["path"],
                    "http_route": route,
                    "http_status": status_code,
                    "duration_ms": round(duration * 1000, 2),
                },
            )
            request_id_var.reset(token)
