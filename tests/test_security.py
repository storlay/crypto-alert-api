import jwt
import pytest

from src.config import get_settings
from src.security import create_access_token
from src.security import hash_password
from src.security import verify_password


def test_password_roundtrip() -> None:
    h = hash_password("super-secret")
    assert verify_password("super-secret", h)
    assert not verify_password("nope", h)


def test_jwt_roundtrip() -> None:
    token = create_access_token(42)
    settings = get_settings()
    payload = jwt.decode(token, settings.jwt_secret, algorithms=[settings.jwt_alg])
    assert payload["sub"] == "42"


def test_jwt_invalid() -> None:
    with pytest.raises(jwt.PyJWTError):
        jwt.decode("garbage", "x", algorithms=["HS256"])
