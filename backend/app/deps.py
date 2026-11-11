"""Sdílené FastAPI závislosti – hlavně ověření přihlášeného uživatele."""
from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy.orm import Session

from .database import get_db
from .models import User
from .security import decode_access_token

_bearer = HTTPBearer(auto_error=False)


def get_current_user(
    creds: HTTPAuthorizationCredentials | None = Depends(_bearer),
    db: Session = Depends(get_db),
) -> User:
    """Každý chráněný endpoint má tuto závislost. Bez platného tokenu vrátí 401."""
    unauthorized = HTTPException(
        status.HTTP_401_UNAUTHORIZED,
        "Přihlášení vypršelo nebo chybí. Přihlas se prosím znovu.",
        headers={"WWW-Authenticate": "Bearer"},
    )
    if creds is None:
        raise unauthorized
    user_id = decode_access_token(creds.credentials)
    if user_id is None:
        raise unauthorized
    user = db.get(User, user_id)
    if user is None:
        raise unauthorized
    return user
