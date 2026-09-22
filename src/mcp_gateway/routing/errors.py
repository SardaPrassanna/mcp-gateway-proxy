class UnknownUpstreamError(KeyError):
    """Raised when an upstream identifier does not match any configured server."""

    def __init__(self, upstream_id: str) -> None:
        self.upstream_id = upstream_id
        super().__init__(f"unknown upstream id: {upstream_id!r}")
