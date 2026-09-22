from mcp_gateway.auth.principal import ANONYMOUS, Principal


def test_anonymous_principal_can_access_any_upstream() -> None:
    assert ANONYMOUS.can_access("database")
    assert ANONYMOUS.can_access("anything")


def test_unrestricted_principal_can_access_any_upstream() -> None:
    principal = Principal(client_id="client-a", allowed_upstreams=None)

    assert principal.can_access("database")
    assert principal.can_access("jira")


def test_restricted_principal_can_only_access_allowed_upstreams() -> None:
    principal = Principal(client_id="client-a", allowed_upstreams=frozenset({"database"}))

    assert principal.can_access("database") is True
    assert principal.can_access("jira") is False


def test_restricted_principal_with_empty_allowlist_can_access_nothing() -> None:
    principal = Principal(client_id="client-a", allowed_upstreams=frozenset())

    assert principal.can_access("database") is False
