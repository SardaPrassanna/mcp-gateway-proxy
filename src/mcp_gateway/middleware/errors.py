class RateLimitExceededError(Exception):
    """Raised when a client has exceeded its configured request rate."""

    def __init__(self, key: str, retry_after_seconds: float) -> None:
        self.key = key
        self.retry_after_seconds = retry_after_seconds
        super().__init__(f"rate limit exceeded for {key!r}")
