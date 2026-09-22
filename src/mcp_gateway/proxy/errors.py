class ProxyError(Exception):
    """Base class for failures while forwarding a request to an upstream."""

    def __init__(self, upstream_name: str, message: str) -> None:
        self.upstream_name = upstream_name
        super().__init__(message)


class UpstreamConnectionError(ProxyError):
    """Raised when the upstream could not be reached."""

    def __init__(self, upstream_name: str) -> None:
        super().__init__(upstream_name, f"failed to connect to upstream {upstream_name!r}")


class UpstreamTimeoutError(ProxyError):
    """Raised when the upstream did not respond within the configured timeout."""

    def __init__(self, upstream_name: str) -> None:
        super().__init__(upstream_name, f"upstream {upstream_name!r} timed out")
