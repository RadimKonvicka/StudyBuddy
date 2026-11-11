"""Registrace, přihlášení a informace o přihlášeném uživateli."""
import time
from collections import defaultdict, deque

from fastapi import APIRouter, Depends, HTTPException, Request, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from ..database import get_db
from ..deps import get_current_user
from ..models import User
from ..schemas import LoginIn, RegisterIn, TokenOut, UserOut
from ..security import DUMMY_HASH, create_access_token, hash_password, verify_password

router = APIRouter(prefix="/api/auth", tags=["Přihlášení"])

# Jednoduchá ochrana proti hádání hesel: max. 8 neúspěšných pokusů za 10 minut z jedné IP.
# (Drží se v paměti procesu – pro maturitní projekt s jedním serverem to stačí.)
_FAILED: dict[str, deque] = defaultdict(deque)
MAX_FAILS, WINDOW_S = 8, 600


def _client_key(request: Request) -> str:
    return request.client.host if request.client else "unknown"


def _check_rate_limit(key: str) -> None:
    q = _FAILED[key]
    now = time.monotonic()
    while q and now - q[0] > WINDOW_S:
        q.popleft()
    if len(q) >= MAX_FAILS:
        raise HTTPException(status.HTTP_429_TOO_MANY_REQUESTS, "Příliš mnoho pokusů. Zkus to za pár minut.")


@router.post("/register", response_model=TokenOut, status_code=201)
def register(body: RegisterIn, db: Session = Depends(get_db)):
    email = body.email.lower()
    if db.scalar(select(User).where(User.email == email)):
        raise HTTPException(status.HTTP_409_CONFLICT, "Účet s tímto e-mailem už existuje.")
    user = User(email=email, password_hash=hash_password(body.password), display_name=body.display_name)
    db.add(user)
    db.commit()
    return TokenOut(access_token=create_access_token(user.id), user=UserOut.model_validate(user))


@router.post("/login", response_model=TokenOut)
def login(body: LoginIn, request: Request, db: Session = Depends(get_db)):
    key = _client_key(request)
    _check_rate_limit(key)
    user = db.scalar(select(User).where(User.email == body.email.lower()))
    # Ověřujeme i při neexistujícím e-mailu (proti dummy hashi), aby čas odpovědi nic neprozradil.
    ok = verify_password(body.password, user.password_hash if user else DUMMY_HASH)
    if not user or not ok:
        _FAILED[key].append(time.monotonic())
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Nesprávný e-mail nebo heslo.")
    _FAILED.pop(key, None)
    return TokenOut(access_token=create_access_token(user.id), user=UserOut.model_validate(user))


@router.get("/me", response_model=UserOut)
def me(user: User = Depends(get_current_user)):
    return user
