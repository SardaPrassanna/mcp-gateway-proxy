import io
import json
import logging

from mcp_gateway.observability import logging as gateway_logging
from mcp_gateway.observability.logging import JsonFormatter, configure_logging


def _make_logger(name: str) -> tuple[logging.Logger, io.StringIO]:
    stream = io.StringIO()
    handler = logging.StreamHandler(stream)
    handler.setFormatter(JsonFormatter())
    logger = logging.getLogger(name)
    logger.handlers = [handler]
    logger.propagate = False
    logger.setLevel(logging.DEBUG)
    return logger, stream


def test_formats_fixed_fields_as_json() -> None:
    logger, stream = _make_logger("test.json.fixed")

    logger.info("hello world")

    payload = json.loads(stream.getvalue())
    assert payload["message"] == "hello world"
    assert payload["level"] == "INFO"
    assert payload["logger"] == "test.json.fixed"
    assert "timestamp" in payload


def test_includes_extra_fields() -> None:
    logger, stream = _make_logger("test.json.extra")

    logger.info("request completed", extra={"correlation_id": "abc-123", "duration_ms": 12.5})

    payload = json.loads(stream.getvalue())
    assert payload["correlation_id"] == "abc-123"
    assert payload["duration_ms"] == 12.5


def test_excludes_standard_log_record_attributes() -> None:
    logger, stream = _make_logger("test.json.standard")

    logger.info("plain message")

    payload = json.loads(stream.getvalue())
    assert "args" not in payload
    assert "filename" not in payload
    assert "msg" not in payload


def test_output_is_single_line_valid_json() -> None:
    logger, stream = _make_logger("test.json.single_line")

    logger.info("multi\nline message", extra={"note": "still one JSON line"})

    lines = stream.getvalue().strip().splitlines()
    assert len(lines) == 1
    json.loads(lines[0])


def test_configure_logging_installs_json_handler_on_root() -> None:
    root = logging.getLogger()
    original_handlers = root.handlers[:]
    original_level = root.level
    original_configured = gateway_logging._configured
    gateway_logging._configured = False
    try:
        configure_logging("DEBUG")
        assert any(isinstance(h.formatter, JsonFormatter) for h in root.handlers)
        assert root.level == logging.DEBUG
    finally:
        root.handlers = original_handlers
        root.setLevel(original_level)
        gateway_logging._configured = original_configured


def test_configure_logging_is_idempotent_about_handler_count() -> None:
    root = logging.getLogger()
    original_handlers = root.handlers[:]
    original_level = root.level
    original_configured = gateway_logging._configured
    gateway_logging._configured = False
    try:
        configure_logging("INFO")
        count_after_first = len(root.handlers)
        configure_logging("INFO")
        assert len(root.handlers) == count_after_first
    finally:
        root.handlers = original_handlers
        root.setLevel(original_level)
        gateway_logging._configured = original_configured
