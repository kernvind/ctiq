import logging
from logging.handlers import RotatingFileHandler
from pathlib import Path

from src.app.core.config import Settings

_CONFIGURED = False


def configure_logging(config: Settings) -> None:
    """Configure root logging. Safe to call multiple times."""
    global _CONFIGURED
    if _CONFIGURED:
        return

    log_dir = Path(config.LOGDIR)
    log_dir.mkdir(parents=True, exist_ok=True)

    formatter = logging.Formatter(
        fmt="%(asctime)s.%(msecs)03d | %(levelname)-7s | %(name)s | "
            "%(filename)s:%(lineno)d - %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )

    # Everything at INFO+ goes here
    app_handler = RotatingFileHandler(
        log_dir / "app.log",
        maxBytes=1024 * 1024,
        backupCount=5,
        encoding="utf-8",
    )
    app_handler.setLevel(logging.INFO)
    app_handler.setFormatter(formatter)

    # ERROR+ duplicated into its own file for easy triage
    error_handler = RotatingFileHandler(
        log_dir / "error.log",
        maxBytes=1024 * 1024,
        backupCount=5,
        encoding="utf-8",
    )
    error_handler.setLevel(logging.ERROR)
    error_handler.setFormatter(formatter)

    # Console too — handy when running locally or in a worker
    console_handler = logging.StreamHandler()
    console_handler.setLevel(logging.INFO)
    console_handler.setFormatter(formatter)

    root = logging.getLogger()
    root.setLevel(logging.INFO)
    root.addHandler(app_handler)
    root.addHandler(error_handler)
    root.addHandler(console_handler)
        # Quiet third-party loggers that emit at INFO too aggressively
    _NOISY_LOGGERS = (
        "httpx",                  # HTTP client used by HF Hub, OpenAI, etc.
        "httpcore",               # underlies httpx; same noise class
        "urllib3",                # used by google-cloud-* and others
        "huggingface_hub",        # model download/cache chatter
        "sentence_transformers",  # model load info we don't care about per-call
        "filelock",               # lock acquire/release noise
    )
    for name in _NOISY_LOGGERS:
        logging.getLogger(name).setLevel(logging.WARNING)

    _CONFIGURED = True