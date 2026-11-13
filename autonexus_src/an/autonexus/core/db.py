"""Database access. SQLite by default; any SQLAlchemy URL (e.g. PostgreSQL) via AUTONEXUS_DB_URL.
All writes run inside write(): one process-wide lock + one transaction, so the audit hash chain and
stock arithmetic cannot interleave. (Multi-process PostgreSQL deployments must additionally take an
advisory lock; see docs/CORE_ARCHITECTURE.md.)"""
import os, threading
from contextlib import contextmanager
from sqlalchemy import create_engine, event
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool
from .models import Base

_lock = threading.RLock()
_engine = None
_Session = None

def configure(url=None):
    global _engine, _Session
    url = url or os.environ.get("AUTONEXUS_DB_URL", "sqlite:///autonexus_core.db")
    kw = {}
    if url.startswith("sqlite"):
        kw["connect_args"] = {"check_same_thread": False}
        if ":memory:" in url or url == "sqlite://":
            kw["poolclass"] = StaticPool
    _engine = create_engine(url, **kw)
    if url.startswith("sqlite"):
        @event.listens_for(_engine, "connect")
        def _fk(conn, _):
            conn.execute("PRAGMA foreign_keys=ON")
    Base.metadata.create_all(_engine)
    _Session = sessionmaker(_engine, expire_on_commit=False)
    return _engine

def engine():
    if _engine is None: configure()
    return _engine

def session() -> Session:
    engine(); return _Session()

@contextmanager
def read():
    s = session()
    try: yield s
    finally: s.close()

@contextmanager
def write():
    with _lock:
        s = session()
        try:
            yield s; s.commit()
        except BaseException:
            s.rollback(); raise
        finally: s.close()
