"""SQLite-backed unified food store. Foods round-trip Food<->row losslessly.

Built offline by etl.run_etl and read at runtime by ranking: candidates() returns
the foods ENMS scores. nutrients is persisted as a JSON blob keyed by canonical keys.
"""
from __future__ import annotations

import json
import sqlite3
from collections.abc import Iterable

from emoeating.data.schema import Food

_SCHEMA = """
CREATE TABLE IF NOT EXISTS foods (
    id         TEXT PRIMARY KEY,
    name       TEXT NOT NULL,
    source     TEXT NOT NULL,
    calories   REAL,
    nutrients  TEXT NOT NULL,
    image_hint TEXT
);
"""

_COLUMNS = "id, name, source, calories, nutrients, image_hint"


def _row_to_food(row: sqlite3.Row) -> Food:
    return Food(
        id=row["id"],
        name=row["name"],
        source=row["source"],
        calories=row["calories"],
        nutrients=json.loads(row["nutrients"]),
        image_hint=row["image_hint"],
    )


def _food_to_params(food: Food) -> tuple:
    return (
        food.id,
        food.name,
        food.source,
        food.calories,
        json.dumps(food.nutrients),
        food.image_hint,
    )


class FoodStore:
    def __init__(self, conn: sqlite3.Connection) -> None:
        self._conn = conn
        self._conn.row_factory = sqlite3.Row
        self._conn.execute(_SCHEMA)

    @classmethod
    def open(cls, path: str = ":memory:") -> "FoodStore":
        return cls(sqlite3.connect(path))

    def upsert_foods(self, foods: Iterable[Food]) -> int:
        written = 0
        with self._conn:
            for food in foods:
                self._conn.execute(
                    f"INSERT OR REPLACE INTO foods ({_COLUMNS}) "
                    f"VALUES (?, ?, ?, ?, ?, ?)",
                    _food_to_params(food),
                )
                written += 1
        return written

    def all_foods(self) -> list[Food]:
        cur = self._conn.execute(f"SELECT {_COLUMNS} FROM foods ORDER BY id")
        return [_row_to_food(r) for r in cur.fetchall()]

    def candidates(self, limit: int | None = None) -> list[Food]:
        sql = f"SELECT {_COLUMNS} FROM foods ORDER BY id"
        params: tuple = ()
        if limit is not None:
            sql += " LIMIT ?"
            params = (limit,)
        cur = self._conn.execute(sql, params)
        return [_row_to_food(r) for r in cur.fetchall()]

    def count(self) -> int:
        return self._conn.execute("SELECT COUNT(*) FROM foods").fetchone()[0]

    def close(self) -> None:
        self._conn.close()
