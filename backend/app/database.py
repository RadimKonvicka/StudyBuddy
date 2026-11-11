"""Připojení k databázi přes SQLAlchemy 2.0.

Lokálně SQLite (soubor studybuddy.db), v produkci PostgreSQL – stačí změnit DATABASE_URL.
"""
from sqlalchemy import create_engine, event
from sqlalchemy.orm import DeclarativeBase, sessionmaker

from .config import get_settings

settings = get_settings()
url = settings.sqlalchemy_url
is_sqlite = url.startswith("sqlite")

engine = create_engine(
    url,
    connect_args={"check_same_thread": False} if is_sqlite else {},
    pool_pre_ping=not is_sqlite,  # u Postgresu ověří, že spojení po uspání serveru žije
)

if is_sqlite:
    # SQLite má cizí klíče ve výchozím stavu vypnuté – zapneme je, aby fungovalo ON DELETE CASCADE.
    @event.listens_for(engine, "connect")
    def _sqlite_fk(dbapi_conn, _):
        cur = dbapi_conn.cursor()
        cur.execute("PRAGMA foreign_keys=ON")
        cur.close()

SessionLocal = sessionmaker(bind=engine, autoflush=False, expire_on_commit=False)


class Base(DeclarativeBase):
    pass


def get_db():
    """FastAPI závislost – každý požadavek dostane vlastní session, která se po něm zavře."""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
