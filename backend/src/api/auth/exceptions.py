"""Internal authentication exceptions mapped to safe API errors."""


class AuthenticationRequiredError(Exception):
    """Raised when a route requires a valid authenticated tenant."""


class AuthenticationUnavailableError(Exception):
    """Raised when the identity provider is unavailable or unconfigured."""
