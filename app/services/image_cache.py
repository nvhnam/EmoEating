"""Persistent SQLite cache for food image URLs — survives app restarts.

Cache lives at data/cache/food_images.db (created automatically).
TTL defaults to 30 days so study participants always see the same images.
Thread-safe: each call opens its own short-lived connection with a 10 s timeout
so concurrent ThreadPoolExecutor prefetches don't hit 'database is locked'.
"""
from __future__ import annotations
import json
import sqlite3
import time
from pathlib import Path

_DB_PATH = Path(__file__).resolve().parent.parent.parent / "data" / "cache" / "food_images.db"
_CACHE_TTL_SECONDS = 30 * 24 * 3600  # 30 days


def _open() -> sqlite3.Connection:
    _DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(str(_DB_PATH), timeout=10, check_same_thread=False)
    conn.execute(
        """CREATE TABLE IF NOT EXISTS food_image_cache (
               food_key   TEXT PRIMARY KEY,
               urls_json  TEXT NOT NULL,
               fetched_at INTEGER NOT NULL
           )"""
    )
    conn.commit()
    return conn


def get_cached_images(food_key: str) -> list[str] | None:
    """Return cached URLs or None if missing / expired."""
    try:
        conn = _open()
        row = conn.execute(
            "SELECT urls_json, fetched_at FROM food_image_cache WHERE food_key = ?",
            (food_key,),
        ).fetchone()
        conn.close()
        if row is None:
            return None
        if time.time() - row[1] > _CACHE_TTL_SECONDS:
            return None
        return json.loads(row[0])
    except Exception:
        return None


def set_cached_images(food_key: str, urls: list[str]) -> None:
    """Persist image URLs for food_key."""
    try:
        conn = _open()
        conn.execute(
            "INSERT OR REPLACE INTO food_image_cache (food_key, urls_json, fetched_at) "
            "VALUES (?, ?, ?)",
            (food_key, json.dumps(urls), int(time.time())),
        )
        conn.commit()
        conn.close()
    except Exception:
        pass
