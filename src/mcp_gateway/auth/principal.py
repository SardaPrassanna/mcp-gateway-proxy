from dataclasses import dataclass


@dataclass(frozen=True)
class Principal:
    """The authenticated identity attached to a request, and what it may reach.

    `allowed_upstreams` mirrors `AuthClient.allowed_upstreams`: `None` means
    any configured upstream is reachable, a set restricts access to exactly
    those upstream names.
    """

    client_id: str
    allowed_upstreams: frozenset[str] | None

    def can_access(self, upstream_name: str) -> bool:
        return self.allowed_upstreams is None or upstream_name in self.allowed_upstreams


ANONYMOUS = Principal(client_id="anonymous", allowed_upstreams=None)
