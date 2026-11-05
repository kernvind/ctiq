import json
import logging

from src.app.core.config import Settings
from src.app.core.request_context import request_id_var
from src.app.core.set_logger import JSONFormatter


def _record(msg="hello %s", args=("world",), level=logging.INFO, exc_info=None, **extra):
    record = logging.LogRecord(
        "app.test", level, __file__, 42, msg, args, exc_info, func="test_fn"
    )
    for key, value in extra.items():
        setattr(record, key, value)
    return record


def _render(record) -> dict:
    line = JSONFormatter().format(record)
    assert "\n" not in line, "one log record must be exactly one line"
    return json.loads(line)


def test_core_fields_are_present_and_message_is_interpolated():
    out = _render(_record())

    assert out["message"] == "hello world"
    assert out["severity"] == "INFO" and out["level"] == "INFO"
    assert out["service"] == "inference-service"
    assert out["logger"] == "app.test"
    assert out["function"] == "test_fn" and out["line_no"] == 42
    assert out["timestamp"].endswith("+00:00")  # timezone-aware UTC


def test_extra_fields_are_merged_at_top_level():
    out = _render(_record(query_len=37, result_count=5))

    assert out["query_len"] == 37
    assert out["result_count"] == 5


def test_extra_cannot_overwrite_core_fields():
    out = _render(_record(service="spoofed"))

    assert out["service"] == "inference-service"


def test_request_id_included_only_inside_a_request():
    assert "request_id" not in _render(_record())

    token = request_id_var.set("req-123")
    try:
        assert _render(_record())["request_id"] == "req-123"
    finally:
        request_id_var.reset(token)


def test_exception_is_serialized_into_the_same_line():
    try:
        raise ValueError("boom")
    except ValueError:
        import sys

        out = _render(_record(level=logging.ERROR, exc_info=sys.exc_info()))

    assert "ValueError: boom" in out["exception"]


def test_non_json_values_do_not_break_logging():
    out = _render(_record(obj=object()))

    assert isinstance(out["obj"], str)


def test_settings_default_to_json_info():
    s = Settings()
    assert s.log_format == "json" and s.log_level == "INFO"
