"""Primitives de autenticación para VulnerableApp Academy.

El módulo no conoce FastAPI ni escribe logs. Las contraseñas y tokens nunca se
almacenan en claro: las primeras usan scrypt (con fallback PBKDF2) y los
segundos se guardan como SHA-256 porque se generan con suficiente entropía.
"""

from __future__ import annotations

import base64
import hashlib
import hmac
import os
import secrets
from dataclasses import dataclass
from typing import Optional


_SCRYPT_N = 2**14
_SCRYPT_R = 8
_SCRYPT_P = 1
_SCRYPT_LENGTH = 32
_PBKDF2_ITERATIONS = 310_000
_SALT_BYTES = 16
_TOKEN_BYTES = 32


def _b64(value: bytes) -> str:
    return base64.urlsafe_b64encode(value).decode("ascii").rstrip("=")


def _unb64(value: str) -> bytes:
    return base64.urlsafe_b64decode(value + "=" * (-len(value) % 4))


def hash_password(password: str) -> str:
    """Return a self-describing password hash.

    ``hashlib.scrypt`` is part of Python's standard library on the supported
    images. The PBKDF2 representation remains available on constrained builds
    where scrypt is not compiled in.
    """

    if not isinstance(password, str) or not password:
        raise ValueError("La contraseña no puede estar vacía")
    salt = os.urandom(_SALT_BYTES)
    try:
        digest = hashlib.scrypt(
            password.encode("utf-8"),
            salt=salt,
            n=_SCRYPT_N,
            r=_SCRYPT_R,
            p=_SCRYPT_P,
            dklen=_SCRYPT_LENGTH,
        )
        return "scrypt${}${}${}${}${}".format(
            _SCRYPT_N,
            _SCRYPT_R,
            _SCRYPT_P,
            _b64(salt),
            _b64(digest),
        )
    except (AttributeError, ValueError, MemoryError):
        digest = hashlib.pbkdf2_hmac(
            "sha256", password.encode("utf-8"), salt, _PBKDF2_ITERATIONS
        )
        return "pbkdf2_sha256${}${}${}".format(
            _PBKDF2_ITERATIONS, _b64(salt), _b64(digest)
        )


def verify_password(password: str, encoded: str) -> bool:
    """Constant-time verification of either supported password format."""

    if not isinstance(password, str) or not isinstance(encoded, str):
        return False
    try:
        parts = encoded.split("$")
        if parts[0] == "scrypt" and len(parts) == 6:
            _, n, r, p, salt_text, digest_text = parts
            candidate = hashlib.scrypt(
                password.encode("utf-8"),
                salt=_unb64(salt_text),
                n=int(n),
                r=int(r),
                p=int(p),
                dklen=len(_unb64(digest_text)),
            )
            return hmac.compare_digest(candidate, _unb64(digest_text))
        if parts[0] == "pbkdf2_sha256" and len(parts) == 4:
            _, iterations, salt_text, digest_text = parts
            candidate = hashlib.pbkdf2_hmac(
                "sha256",
                password.encode("utf-8"),
                _unb64(salt_text),
                int(iterations),
                dklen=len(_unb64(digest_text)),
            )
            return hmac.compare_digest(candidate, _unb64(digest_text))
    except (ValueError, TypeError, IndexError, UnicodeError):
        return False
    return False


def issue_token() -> str:
    """Create a URL-safe random bearer token."""

    return secrets.token_urlsafe(_TOKEN_BYTES)


def token_digest(token: str) -> str:
    """Return the database representation of a bearer token."""

    return hashlib.sha256(token.encode("utf-8")).hexdigest()


def parse_bearer(value: Optional[str]) -> Optional[str]:
    """Extract a bearer token without accepting other authorization schemes."""

    if not value or not isinstance(value, str):
        return None
    scheme, separator, token = value.partition(" ")
    if separator != " " or scheme.lower() != "bearer" or not token:
        return None
    token = token.strip()
    if not token or len(token) > 256:
        return None
    return token


@dataclass(frozen=True)
class TokenRecord:
    token: str
    digest: str

    @classmethod
    def create(cls) -> "TokenRecord":
        token = issue_token()
        return cls(token=token, digest=token_digest(token))
