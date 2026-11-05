"""Per-request context shared by logging and middleware.

A ContextVar (not a global) so concurrent requests on the same event loop each see their
own request id; asyncio copies the context into every task spawned while handling a request.
"""
from contextvars import ContextVar
from typing import Optional

request_id_var: ContextVar[Optional[str]] = ContextVar("request_id", default=None)
