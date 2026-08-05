"""Cookie authentication middleware."""

from __future__ import annotations

from starlette.middleware.base import BaseHTTPMiddleware, RequestResponseEndpoint
from starlette.requests import Request
from starlette.responses import Response

from ...config import settings
from .context import AuthenticationContext, set_authentication_context
from .exceptions import InvalidAuthenticationTokenError
from .security import decode_access_token


class AuthenticationMiddleware(BaseHTTPMiddleware):
    """Resolve a signed session cookie into trusted per-request identity state."""

    async def dispatch(self, request: Request, call_next: RequestResponseEndpoint) -> Response:
        """Authenticate the configured cookie while leaving public routes anonymous."""
        set_authentication_context(request, None)
        token = request.cookies.get(settings.auth_cookie_name)
        if token:
            try:
                payload = decode_access_token(token)
            except InvalidAuthenticationTokenError:
                pass
            else:
                set_authentication_context(
                    request,
                    AuthenticationContext(tenant_id=payload.tenant_id),
                )
        return await call_next(request)
