"""JWT validado e limitação de pedidos de acesso sem registrar credenciais."""

import hashlib
import time
from datetime import UTC, datetime, timedelta
from threading import Lock
from uuid import uuid4

import jwt
from pydantic import EmailStr, TypeAdapter, ValidationError

from settings import Settings


class RateLimitError(Exception):
    def __init__(self, retry_after: int):
        self.retry_after = max(1, retry_after)


def require_secret(settings: Settings) -> str:
    secret = settings.jwt_secret
    if not secret or len(secret.encode()) < 32 or secret == "super-secreto-mudar-em-producao":
        raise ValueError("Configure JWT_SECRET com pelo menos 32 bytes aleatórios antes de iniciar a API")
    return secret


def issue_token(email: str, settings: Settings) -> str:
    now = datetime.now(UTC)
    return jwt.encode(
        {"sub": email, "iat": now, "exp": now + timedelta(seconds=settings.jwt_ttl_seconds), "jti": str(uuid4())},
        require_secret(settings),
        algorithm="HS256",
    )


def decode_token(token: str, settings: Settings) -> str:
    payload = jwt.decode(token, require_secret(settings), algorithms=["HS256"], options={"require": ["sub", "exp"]})
    try:
        return str(TypeAdapter(EmailStr).validate_python(payload["sub"]))
    except ValidationError as exc:
        raise jwt.InvalidTokenError("Token sem e-mail válido") from exc


def rate_keys(email: str, client_ip: str, settings: Settings) -> list[tuple[str, int]]:
    return [
        ("email:" + hashlib.sha256(email.lower().encode()).hexdigest(), settings.auth_max_requests),
        ("ip:" + hashlib.sha256(client_ip.encode()).hexdigest(), settings.auth_ip_max_requests),
    ]


class LocalRateLimiter:
    """Fallback limitado para a API síncrona sem PostgreSQL (por processo)."""

    def __init__(self):
        self._entries: dict[str, tuple[int, float]] = {}
        self._lock = Lock()

    def reserve(self, keys: list[tuple[str, int]], window_seconds: int) -> None:
        now = time.monotonic()
        with self._lock:
            self._entries = {key: value for key, value in self._entries.items() if value[1] > now}
            new_keys = sum(key not in self._entries for key, _ in keys)
            if len(self._entries) + new_keys > 10000:
                raise RateLimitError(window_seconds)
            for key, limit in keys:
                count, until = self._entries.get(key, (0, now + window_seconds))
                if count >= limit:
                    raise RateLimitError(int(until - now) + 1)
            for key, _ in keys:
                count, until = self._entries.get(key, (0, now + window_seconds))
                self._entries[key] = count + 1, until
