"""Security-focused unit tests for API key authentication (Phase 9).

Complements test_authenticator.py with an attacker's-eye view: timing-safe
comparison, malformed/hostile input, and secret-leakage checks.
"""

import hmac
from unittest.mock import patch

import pytest

from mcp_gateway.auth.authenticator import ApiKeyAuthenticator
from mcp_gateway.auth.errors import AuthenticationError
from mcp_gateway.config.auth import AuthClient, AuthConfig

_SINGLE_KEY_CONFIG = AuthConfig(enabled=True, provider="api_key", api_key="super-secret-key")
_MULTI_CLIENT_CONFIG = AuthConfig(
    enabled=True,
    provider="api_key",
    clients=[
        AuthClient(client_id="client-a", api_key="key-a-secret", allowed_upstreams={"database"}),
        AuthClient(client_id="client-b", api_key="key-b-secret"),
    ],
)


# --- 7. timing-safe key comparison behavior is used -------------------------


def test_single_key_mode_uses_hmac_compare_digest() -> None:
    authenticator = ApiKeyAuthenticator(_SINGLE_KEY_CONFIG)

    with patch("mcp_gateway.auth.authenticator.hmac.compare_digest") as spy:
        spy.return_value = True
        authenticator.authenticate("anything")

    spy.assert_called_once_with(b"anything", b"super-secret-key")


def test_multi_client_mode_uses_hmac_compare_digest_for_each_candidate() -> None:
    authenticator = ApiKeyAuthenticator(_MULTI_CLIENT_CONFIG)

    with patch("mcp_gateway.auth.authenticator.hmac.compare_digest") as spy:
        spy.return_value = False
        with pytest.raises(AuthenticationError):
            authenticator.authenticate("not-a-real-key")

    assert spy.call_count == 2
    called_with = {call.args for call in spy.call_args_list}
    assert (b"not-a-real-key", b"key-a-secret") in called_with
    assert (b"not-a-real-key", b"key-b-secret") in called_with


def test_wrong_key_of_different_length_is_still_rejected_via_compare_digest() -> None:
    """A naive `==` short-circuits on length; compare_digest must still be used."""
    authenticator = ApiKeyAuthenticator(_SINGLE_KEY_CONFIG)

    with (
        patch(
            "mcp_gateway.auth.authenticator.hmac.compare_digest", wraps=hmac.compare_digest
        ) as spy,
        pytest.raises(AuthenticationError),
    ):
        authenticator.authenticate("x")

    spy.assert_called_once()


# --- 9. malformed authentication headers ------------------------------------


def test_non_ascii_key_is_rejected_cleanly_not_raised() -> None:
    """Regression test: hmac.compare_digest raises TypeError on non-ASCII str,
    which must never escape authenticate() as an unhandled exception."""
    authenticator = ApiKeyAuthenticator(_SINGLE_KEY_CONFIG)

    with pytest.raises(AuthenticationError):
        authenticator.authenticate("ключ-unicode-☃")


def test_empty_string_key_is_treated_as_missing() -> None:
    authenticator = ApiKeyAuthenticator(_SINGLE_KEY_CONFIG)

    with pytest.raises(AuthenticationError):
        authenticator.authenticate("")


def test_whitespace_only_key_is_rejected() -> None:
    authenticator = ApiKeyAuthenticator(_SINGLE_KEY_CONFIG)

    with pytest.raises(AuthenticationError):
        authenticator.authenticate("   ")


def test_key_with_surrounding_whitespace_is_not_silently_trimmed() -> None:
    """The gateway must not normalize presented keys; that would let a key with
    incidental whitespace succeed when the operator configured an exact value."""
    authenticator = ApiKeyAuthenticator(_SINGLE_KEY_CONFIG)

    with pytest.raises(AuthenticationError):
        authenticator.authenticate(" super-secret-key ")


def test_very_long_key_is_rejected_without_error() -> None:
    authenticator = ApiKeyAuthenticator(_SINGLE_KEY_CONFIG)

    with pytest.raises(AuthenticationError):
        authenticator.authenticate("x" * 100_000)


def test_key_containing_null_byte_is_rejected_without_error() -> None:
    authenticator = ApiKeyAuthenticator(_SINGLE_KEY_CONFIG)

    with pytest.raises(AuthenticationError):
        authenticator.authenticate("super-secret-key\x00")


# --- 6. API key is not exposed in logs/errors --------------------------------


@pytest.mark.parametrize(
    "presented_key",
    ["wrong-guess", "", "   ", "ключ-unicode", "x" * 1000],
)
def test_authentication_error_never_contains_configured_secrets(presented_key: str) -> None:
    authenticator = ApiKeyAuthenticator(_MULTI_CLIENT_CONFIG)

    try:
        authenticator.authenticate(presented_key)
    except AuthenticationError as exc:
        assert "key-a-secret" not in str(exc)
        assert "key-b-secret" not in str(exc)
    else:
        pytest.fail("expected AuthenticationError")


def test_authentication_error_never_contains_the_presented_key_either() -> None:
    """Echoing the *attempted* key back in an error would itself be a leak
    surface (e.g. into shared logs) if a legitimate key were mistyped."""
    authenticator = ApiKeyAuthenticator(_SINGLE_KEY_CONFIG)

    try:
        authenticator.authenticate("almost-super-secret-key-guess")
    except AuthenticationError as exc:
        assert "almost-super-secret-key-guess" not in str(exc)
    else:
        pytest.fail("expected AuthenticationError")
