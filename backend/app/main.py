"""Vstupní bod backendu StudyBuddy.

Spuštění (ze složky backend):  uvicorn app.main:app --reload
Dokumentace API:               http://localhost:8000/docs
"""
from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from . import models  # noqa: F401  – registrace tabulek před create_all
from .config import get_settings
from .database import Base, engine
from .routers import auth

settings = get_settings()

# Vytvoří chybějící tabulky (pro maturitní projekt stačí; při změně schématu smaž lokální DB).
Base.metadata.create_all(bind=engine)

app = FastAPI(title="StudyBuddy API", version="2.0.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_list,
    allow_credentials=False,  # token posíláme v hlavičce, ne v cookie
    allow_methods=["*"],
    allow_headers=["*"],
)

# Překlad nejčastějších validačních chyb do češtiny (Pydantic je hlásí anglicky).
_FIELD_NAMES = {"email": "E-mail", "password": "Heslo", "display_name": "Jméno", "title": "Název"}


def _czech_error(err: dict) -> str:
    field = str(err.get("loc", ["", ""])[-1])
    name = _FIELD_NAMES.get(field, field)
    typ = err.get("type", "")
    ctx = err.get("ctx") or {}
    if typ == "missing":
        return f"{name}: povinný údaj chybí."
    if typ == "string_too_short":
        return f"{name}: musí mít aspoň {ctx.get('min_length')} znaků."
    if typ == "string_too_long":
        return f"{name}: může mít nejvýš {ctx.get('max_length')} znaků."
    if field == "email" or "email" in typ:
        return "E-mail nemá platný tvar."
    if typ == "value_error":
        return f"{name}: {str(ctx.get('error', err.get('msg', '')))}"
    return f"{name}: neplatná hodnota."


@app.exception_handler(RequestValidationError)
async def validation_handler(_: Request, exc: RequestValidationError):
    errors = exc.errors()
    return JSONResponse(status_code=422, content={"detail": _czech_error(errors[0]) if errors else "Neplatný vstup."})


app.include_router(auth.router)


@app.get("/api/health", tags=["Systém"])
def health():
    return {"status": "ok"}
