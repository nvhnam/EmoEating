"""
One-time backfill: populate omega3_mg for existing Open Food Facts records.

The OFF loader originally omitted "omega-3-fat_100g" from USECOLS, leaving
omega3_mg=NULL for all OFF foods already in the DB. This script reads the raw
TSV, builds a product_name→omega3_mg lookup, and issues batched UPDATEs.

Run once from the project root:
    python scripts/fix_omega3.py

Idempotent: the WHERE clause guards `fn.omega3_mg IS NULL`, so re-running
never overwrites a value that was already populated.
"""

from __future__ import annotations

import sys
import os
from pathlib import Path

PROJECT_ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(PROJECT_ROOT / "app"))
sys.path.insert(0, str(PROJECT_ROOT))

import pandas as pd
from sqlalchemy import create_engine, text
from tqdm import tqdm

from etl.config import DB_URL, OPENFOODFACTS_FILE
from etl.transformers.nutrient_normalizer import compute_normalization_cache

CHUNK_SIZE = 50_000
BATCH_SIZE = 100
OFF_USECOLS = ["product_name", "omega-3-fat_100g"]


def _build_lookup(tsv_path: Path) -> dict[str, float]:
    """Read TSV in chunks; return {lower_product_name: omega3_mg} for valid rows."""
    lookup: dict[str, float] = {}

    reader = pd.read_csv(
        tsv_path,
        sep="\t",
        usecols=lambda c: c in OFF_USECOLS,
        low_memory=False,
        chunksize=CHUNK_SIZE,
        on_bad_lines="skip",
    )

    for chunk in tqdm(reader, desc="Scanning TSV for omega-3 values"):
        if "omega-3-fat_100g" not in chunk.columns:
            continue
        sub = chunk[chunk["omega-3-fat_100g"].notna()].copy()
        sub["omega-3-fat_100g"] = pd.to_numeric(sub["omega-3-fat_100g"], errors="coerce")
        # omega-3-fat_100g is in g/100g; DECIMAL(8,3) holds up to 99999.999 mg.
        # Upper bound: 99.999 g/100g × 1000 = 99999.0 mg — any higher is biologically
        # impossible (omega-3 cannot exceed total fat, which is ≤ 100 g/100g) and
        # would overflow the column.
        sub = sub[
            sub["omega-3-fat_100g"].notna()
            & (sub["omega-3-fat_100g"] >= 0)
            & (sub["omega-3-fat_100g"] <= 99.999)
        ]

        for _, row in sub.iterrows():
            name = str(row.get("product_name", "")).strip()[:255]
            if not name:
                continue
            key = name.lower()
            if key not in lookup:
                # Keep first occurrence — earlier rows tend to be more curated
                lookup[key] = round(row["omega-3-fat_100g"] * 1000.0, 3)  # g → mg

    return lookup


def _update_db(engine, lookup: dict[str, float]) -> int:
    """Issue batched UPDATE for OFF foods whose omega3_mg is currently NULL."""
    update_sql = text("""
        UPDATE food_nutrients fn
        JOIN foods f ON f.id = fn.food_id
        SET fn.omega3_mg = :omega3_mg,
            fn.data_completeness = fn.data_completeness + 1
        WHERE LOWER(f.name) = :name_lower
          AND f.source_dataset = 'openfoodfacts'
          AND fn.omega3_mg IS NULL
    """)

    items = list(lookup.items())
    total_updated = 0

    with engine.connect() as conn:
        for i, (name_lower, omega3_mg) in enumerate(tqdm(items, desc="Updating DB records")):
            result = conn.execute(update_sql, {
                "omega3_mg": omega3_mg,
                "name_lower": name_lower,
            })
            total_updated += result.rowcount
            if (i + 1) % BATCH_SIZE == 0:
                conn.commit()
        conn.commit()

    return total_updated


def _print_validation(engine) -> None:
    """Print populated vs. still-NULL summary for OFF records."""
    sql = text("""
        SELECT
            SUM(fn.omega3_mg IS NOT NULL) AS populated,
            SUM(fn.omega3_mg IS NULL)     AS still_null,
            COUNT(*)                      AS total
        FROM food_nutrients fn
        JOIN foods f ON f.id = fn.food_id
        WHERE f.source_dataset = 'openfoodfacts'
    """)
    with engine.connect() as conn:
        row = conn.execute(sql).fetchone()
    print(
        f"\nValidation — Open Food Facts omega3_mg:\n"
        f"  Populated : {row.populated}\n"
        f"  Still NULL: {row.still_null}\n"
        f"  Total     : {row.total}\n"
    )


def main() -> None:
    tsv_path = Path(OPENFOODFACTS_FILE)
    if not tsv_path.exists():
        sys.exit(f"ERROR: TSV not found at {tsv_path}")

    print(f"Source: {tsv_path}")
    print("Step 1/3 — Building omega-3 lookup from TSV...")
    lookup = _build_lookup(tsv_path)
    print(f"  Found {len(lookup)} unique product names with omega-3 values.")

    if not lookup:
        print("No omega-3 data found in TSV. Nothing to update.")
        return

    engine = create_engine(DB_URL, pool_pre_ping=True)

    print("Step 2/3 — Updating food_nutrients in DB...")
    updated = _update_db(engine, lookup)
    print(f"  Updated {updated} rows.")

    print("Step 3/3 — Refreshing normalization_cache...")
    n = compute_normalization_cache(engine)
    print(f"  normalization_cache: {n} rows upserted.")

    _print_validation(engine)
    print("Done.")


if __name__ == "__main__":
    main()
