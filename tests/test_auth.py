from dataclasses import replace
from datetime import UTC, datetime, timedelta

import jwt
import pytest

import auth
from settings import load_settings


@pytest.fixture
def configuration():
    return replace(load_settings(), jwt_secret="test-only-secret-not-for-production-123456")


@pytest.mark.parametrize("secret", [None, "", "short", "super-secreto-mudar-em-producao"])
def test_rejects_missing_weak_or_old_default_secret(configuration, secret):
    with pytest.raises(ValueError, match="JWT_SECRET"):
        auth.require_secret(replace(configuration, jwt_secret=secret))


def test_token_has_expiry_and_verified_email_subject(configuration):
    token = auth.issue_token("alice@example.com", configuration)
    assert auth.decode_token(token, configuration) == "alice@example.com"
    claims = jwt.decode(token, configuration.jwt_secret, algorithms=["HS256"])
    assert claims["exp"] > claims["iat"]
    assert claims["jti"]


@pytest.mark.parametrize(
    "claims",
    [
        {"sub": "alice@example.com"},
        {"exp": datetime.now(UTC) + timedelta(hours=1)},
        {"sub": "invalid email", "exp": datetime.now(UTC) + timedelta(hours=1)},
        {"sub": "alice@example.com", "exp": datetime.now(UTC) - timedelta(seconds=1)},
    ],
)
def test_rejects_missing_invalid_or_expired_claims(configuration, claims):
    token = jwt.encode(claims, configuration.jwt_secret, algorithm="HS256")
    with pytest.raises(jwt.InvalidTokenError):
        auth.decode_token(token, configuration)


def test_local_limiter_blocks_repeated_email_and_expires(configuration, monkeypatch):
    now = [100.0]
    monkeypatch.setattr(auth.time, "monotonic", lambda: now[0])
    limiter = auth.LocalRateLimiter()
    keys = auth.rate_keys("alice@example.com", "127.0.0.1", replace(configuration, auth_max_requests=1))
    limiter.reserve(keys, 60)
    with pytest.raises(auth.RateLimitError) as error:
        limiter.reserve(keys, 60)
    assert error.value.retry_after > 0
    assert all("alice@example.com" not in key and "127.0.0.1" not in key for key, _ in keys)
    now[0] += 61
    limiter.reserve(keys, 60)
