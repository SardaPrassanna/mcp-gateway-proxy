"""Structured audit events for security- and policy-relevant decisions.

Audit events are distinct from ordinary application logs: each one names a
discrete decision the gateway made (authentication outcome, authorization
outcome, rate-limit outcome, routing outcome) with identifiers attached, so
they can be queried or alerted on independently of general request logs.
"""

import logging

AUDIT_LOGGER_NAME = "mcp_gateway.audit"

_audit_logger = logging.getLogger(AUDIT_LOGGER_NAME)


def audit_event(event: str, **fields: object) -> None:
    """Emit a structured audit event.

    Callers must never pass secret material (API keys, tokens, full request
    or response bodies) as a field — only identifiers and outcomes belong in
    an audit event.
    """
    _audit_logger.info(event, extra={"event": event, **fields})
