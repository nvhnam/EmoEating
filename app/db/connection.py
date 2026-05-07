"""
MySQL connection pool via SQLAlchemy.
Reads credentials from environment variables (or .env file).
"""

from __future__ import annotations

import os
import sys
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from sqlalchemy import create_engine, text
from sqlalchemy.engine import URL
from sqlalchemy.pool import QueuePool
from dotenv import load_dotenv

load_dotenv()

_engine = None


def get_engine():
    """Return singleton SQLAlchemy engine."""
    global _engine
    if _engine is None:
        from config import DB_HOST, DB_PORT, DB_NAME, DB_USER, DB_PASS
        url = URL.create(
            drivername="mysql+pymysql",
            username=DB_USER,
            password=DB_PASS,
            host=DB_HOST,
            port=DB_PORT,
            database=DB_NAME,
            query={"charset": "utf8mb4"},
        )
        _engine = create_engine(
            url,
            poolclass=QueuePool,
            pool_size=5,
            max_overflow=10,
            pool_pre_ping=True,
            echo=False,
        )
    return _engine


def get_connection():
    """Return a raw connection from the pool."""
    return get_engine().connect()


def test_connection() -> bool:
    """Return True if DB is reachable, False otherwise."""
    try:
        with get_engine().connect() as conn:
            conn.execute(text("SELECT 1"))
        return True
    except Exception:
        return False
