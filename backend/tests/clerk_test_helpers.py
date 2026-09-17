"""Offline signing keys for exercising the real Clerk token verifier."""

from datetime import UTC, datetime
from typing import Any

import jwt
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric import rsa

PRIVATE_KEY = rsa.generate_private_key(public_exponent=65537, key_size=2048)
PUBLIC_KEY = (
    PRIVATE_KEY.public_key()
    .public_bytes(serialization.Encoding.PEM, serialization.PublicFormat.SubjectPublicKeyInfo)
    .decode()
)


def session_token(subject: str, **changes: Any) -> str:
    """Issue an offline RS256 fixture with normal Clerk session claims."""
    now = int(datetime.now(UTC).timestamp())
    claims = {
        "sub": subject,
        "sid": "sess_fixture",
        "iss": "https://clerk.example.com",
        "azp": "http://localhost:3000",
        "iat": now,
        "nbf": now,
        "exp": now + 60,
        "v": 2,
    }
    claims.update(changes)
    for key in [key for key, value in claims.items() if value is None]:
        del claims[key]
    return jwt.encode(claims, PRIVATE_KEY, algorithm="RS256", headers={"kid": "offline"})
