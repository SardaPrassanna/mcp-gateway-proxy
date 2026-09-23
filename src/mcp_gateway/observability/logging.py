"""Structured JSON logging for the gateway.

All application logging goes through this module's formatter so that every
log line — access logs, audit events, proxy warnings — is a single JSON
object with a consistent shape, suitable for ingestion by a log pipeline.
"""

import json
import logging
from datetime import UTC, datetime

_RESERVED_LOG_RECORD_ATTRS = frozenset(
    logging.LogRecord("", 0, "", 0, "", (), None).__dict__.keys()
) | {"message", "asctime"}

_configured = False


class JsonFormatter(logging.Formatter):
    """Renders a log record as a single-line JSON object.

    Only the fixed fields (timestamp, level, logger, message) and whatever a
    caller explicitly passed via ``extra=`` are included, so structured
    context such as a correlation id or a request duration survives into the
    output instead of being flattened into an interpolated string.
    """

    def format(self, record: logging.LogRecord) -> str:
        payload: dict[str, object] = {
            "timestamp": datetime.fromtimestamp(record.created, tz=UTC).isoformat(),
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
        }
        for key, value in record.__dict__.items():
            if key not in _RESERVED_LOG_RECORD_ATTRS:
                payload[key] = value
        if record.exc_info:
            payload["exc_info"] = self.formatException(record.exc_info)
        return json.dumps(payload, default=str)


def configure_logging(level: str) -> None:
    """Install a JSON-formatted handler on the root logger, once per process.

    Idempotent so that repeated calls (e.g. across worker reloads) never
    stack duplicate handlers; only the level is refreshed on later calls.
    """
    global _configured
    root = logging.getLogger()
    root.setLevel(level)
    if _configured:
        return
    handler = logging.StreamHandler()
    handler.setFormatter(JsonFormatter())
    root.addHandler(handler)
    _configured = True
