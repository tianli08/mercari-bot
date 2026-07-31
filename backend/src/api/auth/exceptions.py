"""Internal authentication exceptions mapped to safe API errors."""


class InvalidCredentialsError(Exception):
    """Raised when login credentials or account eligibility are invalid."""


class AuthenticationRequiredError(Exception):
    """Raised when a route requires a valid authenticated tenant."""


class InvalidAuthenticationTokenError(Exception):
    """Raised when a session token cannot be trusted."""
