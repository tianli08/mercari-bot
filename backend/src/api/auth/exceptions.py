"""Internal authentication exceptions mapped to safe API errors."""


class InvalidCredentialsError(Exception):
    """Raised when login credentials or account eligibility are invalid."""


class AuthenticationRequiredError(Exception):
    """Raised when a route requires a valid authenticated tenant."""


class InvalidAuthenticationTokenError(Exception):
    """Raised when a session token cannot be trusted."""


class RateLimitedError(Exception):
    """Raised when an unauthenticated auth client has exhausted its request budget."""

    def __init__(self, retry_after_seconds: int) -> None:
        """Store a positive Retry-After interval in seconds."""
        self.retry_after_seconds = max(1, int(retry_after_seconds))
        super().__init__("Too many requests")
