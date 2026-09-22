import pytest
from pydantic import ValidationError

from mcp_gateway.config.upstream import UpstreamServerConfig


def test_upstream_valid_config() -> None:
    upstream = UpstreamServerConfig(name="example", url="http://localhost:9000")

    assert upstream.name == "example"
    assert str(upstream.url) == "http://localhost:9000/"
    assert upstream.timeout_seconds is None


def test_upstream_rejects_invalid_url() -> None:
    with pytest.raises(ValidationError):
        UpstreamServerConfig(name="example", url="not-a-url")


def test_upstream_rejects_invalid_name_characters() -> None:
    with pytest.raises(ValidationError):
        UpstreamServerConfig(name="bad name!", url="http://localhost:9000")


def test_upstream_rejects_empty_name() -> None:
    with pytest.raises(ValidationError):
        UpstreamServerConfig(name="", url="http://localhost:9000")


def test_upstream_rejects_non_positive_timeout() -> None:
    with pytest.raises(ValidationError):
        UpstreamServerConfig(name="example", url="http://localhost:9000", timeout_seconds=0)
