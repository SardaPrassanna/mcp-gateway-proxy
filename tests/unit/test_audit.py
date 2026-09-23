import logging

import pytest

from mcp_gateway.observability.audit import AUDIT_LOGGER_NAME, audit_event


def test_audit_event_logs_event_name_as_message(caplog: pytest.LogCaptureFixture) -> None:
    with caplog.at_level(logging.INFO, logger=AUDIT_LOGGER_NAME):
        audit_event("test_event")

    assert caplog.records[-1].message == "test_event"


def test_audit_event_attaches_extra_fields_to_the_record(caplog: pytest.LogCaptureFixture) -> None:
    with caplog.at_level(logging.INFO, logger=AUDIT_LOGGER_NAME):
        audit_event("authentication_succeeded", correlation_id="corr-1", client_id="client-a")

    record = caplog.records[-1]
    assert record.event == "authentication_succeeded"  # type: ignore[attr-defined]
    assert record.correlation_id == "corr-1"  # type: ignore[attr-defined]
    assert record.client_id == "client-a"  # type: ignore[attr-defined]


def test_audit_event_uses_the_dedicated_audit_logger(caplog: pytest.LogCaptureFixture) -> None:
    with caplog.at_level(logging.INFO, logger=AUDIT_LOGGER_NAME):
        audit_event("some_event")

    assert caplog.records[-1].name == AUDIT_LOGGER_NAME
