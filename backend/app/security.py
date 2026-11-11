"""Hashování hesel (Argon2) a JWT tokeny.

Argon2id je vítěz soutěže Password Hashing Competition – je záměrně pomalý a paměťově náročný,
takže hrubá síla (zkoušení hesel) je drahá. Heslo se nikdy neukládá v čitelné podobě.

JWT (JSON Web Token) je podepsaný řetězec s ID uživatele a časem vypršení. Server si ho
nemusí pamatovat – podpis HMAC-SHA256 se SECRET_KEY zaručí, že token nikdo nezfalšoval.
"""
from datetime import datetime, timedelta, timezone

import jwt
from argon2 import PasswordHasher
from argon2.exceptions import InvalidHashError, VerifyMismatchError

from .config import get_settings

_hasher = PasswordHasher()
ALGORITHM = "HS256"


def hash_password(password: str) -> str:
    return _hasher.hash(password)


def verify_password(password: str, password_hash: str) -> bool:
    try:
        return _hasher.verify(password_hash, password)
    except (VerifyMismatchError, InvalidHashError):
        return False


# Hash náhodného hesla – používá se, když e-mail neexistuje, aby odpověď trvala stejně dlouho
# a útočník z rychlosti nepoznal, které e-maily jsou registrované.
DUMMY_HASH = _hasher.hash("studybuddy-dummy-password")


def create_access_token(user_id: int) -> str:
    settings = get_settings()
    now = datetime.now(timezone.utc)
    payload = {
        "sub": str(user_id),
        "iat": now,
        "exp": now + timedelta(minutes=settings.access_token_minutes),
    }
    return jwt.encode(payload, settings.secret_key, algorithm=ALGORITHM)


def decode_access_token(token: str) -> int | None:
    """Vrátí ID uživatele, nebo None pokud je token neplatný či prošlý."""
    try:
        payload = jwt.decode(token, get_settings().secret_key, algorithms=[ALGORITHM])
        return int(payload["sub"])
    except (jwt.PyJWTError, KeyError, ValueError):
        return None
