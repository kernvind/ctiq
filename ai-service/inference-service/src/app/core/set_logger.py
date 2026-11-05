"""Process-wide logging: one JSON object per line on stdout.

Containers should log to stdout/stderr and let the platform ship it (Docker -> Alloy -> Loki
today; Cloud Logging / Datadog / ELK later with no code change). Log *files* inside a
container are lost on redeploy and invisible to every shipper, so there are none here.

Field names follow the conventions already used by api-core's pino config: `severity` is the
Cloud Logging key, `message` the text. Extra context passed as ``logger.info("...", extra={...})``
is merged into the top level of the JSON object. Never put raw user text (search queries,
patient profiles) in a message or in `extra` — log lengths, counts and ids instead.
"""
import json
import logging
import sys
from datetime import datetime, timezone

from src.app.core.config import Settings
from src.app.core.request_context import request_id_var

_CONFIGURED = False

# Attributes every LogRecord carries; anything else on a record arrived via `extra=`.
_STANDARD_ATTRS = frozenset(
    vars(logging.LogRecord("", 0, "", 0, "", (), None))
) | {"message", "asctime", "taskName"}

_TEXT_FORMAT = (
    "%(asctime)s.%(msecs)03d | %(levelname)-7s | %(name)s | "
    "%(filename)s:%(lineno)d - %(message)s"
)

# Quiet third-party loggers that emit at INFO too aggressively
_NOISY_LOGGERS = (
    "httpx",                  # HTTP client used by HF Hub, OpenAI, etc.
    "httpcore",               # underlies httpx; same noise class
    "urllib3",                # used by google-cloud-* and others
    "huggingface_hub",        # model download/cache chatter
    "sentence_transformers",  # model load info we don't care about per-call
    "filelock",               # lock acquire/release noise
)


class JSONFormatter(logging.Formatter):
    """Render a LogRecord as a single-line JSON object for ELK / Loki / Datadog / Cloud Logging."""

    def __init__(self, service: str = "inference-service") -> None:
        super().__init__()
        self._service = service

    def format(self, record: logging.LogRecord) -> str:
        payload: dict[str, object] = {
            "timestamp": datetime.fromtimestamp(record.created, tz=timezone.utc).isoformat(
                timespec="milliseconds"
            ),
            "severity": record.levelname,
            "level": record.levelname,
            "service": self._service,
            "logger": record.name,
            "message": record.getMessage(),
            "module": record.module,
            "function": record.funcName,
            "line_no": record.lineno,
        }
        request_id = request_id_var.get()
        if request_id:
            payload["request_id"] = request_id
        if record.exc_info:
            payload["exception"] = self.formatException(record.exc_info)
        if record.stack_info:
            payload["stack"] = self.formatStack(record.stack_info)
        # Custom fields from `extra=`; the core keys above always win on a collision.
        for key, value in record.__dict__.items():
            if key not in _STANDARD_ATTRS and not key.startswith("_"):
                payload.setdefault(key, value)
        return json.dumps(payload, default=str)


def configure_logging(config: Settings) -> None:
    """Configure root logging. Safe to call multiple times."""
    global _CONFIGURED
    if _CONFIGURED:
        return

    handler = logging.StreamHandler(sys.stdout)
    if config.log_format == "text":  # human-readable, for local development
        handler.setFormatter(logging.Formatter(_TEXT_FORMAT, datefmt="%Y-%m-%d %H:%M:%S"))
    else:
        handler.setFormatter(JSONFormatter())

    root = logging.getLogger()
    root.handlers[:] = [handler]
    root.setLevel(config.log_level.upper())

    # uvicorn installs its own handlers/formats at startup (before this module runs). Route its
    # server logs through ours so they're JSON too. Its access log is disabled: it prints the
    # full URL including `?q=<search text>`, and ObservabilityMiddleware emits a
    # query-string-free access line instead.
    for name in ("uvicorn", "uvicorn.error"):
        server_logger = logging.getLogger(name)
        server_logger.handlers.clear()
        server_logger.propagate = True
    access_logger = logging.getLogger("uvicorn.access")
    access_logger.handlers.clear()
    access_logger.propagate = False
    access_logger.disabled = True

    for name in _NOISY_LOGGERS:
        logging.getLogger(name).setLevel(logging.WARNING)

    _CONFIGURED = True
