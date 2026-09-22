class AuthenticationError(Exception):
    """Raised when a request does not carry a valid credential."""


class AuthorizationError(Exception):
    """Raised when an authenticated principal may not access a given upstream."""

    def __init__(self, client_id: str, upstream_name: str) -> None:
        self.client_id = client_id
        self.upstream_name = upstream_name
        super().__init__(f"client {client_id!r} is not authorized for upstream {upstream_name!r}")
