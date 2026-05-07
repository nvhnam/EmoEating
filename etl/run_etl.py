"""
Master ETL runner.
Usage: python etl/run_etl.py [--datasets usda,foodcom,epicurious,indian,off]

Loads each dataset in the correct dependency order:
    1. USDA (ingredients â€” needed for Indian fuzzy matching)
    2. Food.com (primary meal source)
    3. Epicurious
    4. Indian Food (depends on USDA)
    5. Open Food Facts

Then computes normalization_cache.
"""

from __future__ import annotations

import argparse
import sys
import os
from pathlib import Path

# Resolve project root
PROJECT_ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(PROJECT_ROOT / "app"))
sys.path.insert(0, str(PROJECT_ROOT))

from sqlalchemy import create_engine, text
from etl.config import DB_URL, USDA_FILE, FOODCOM_RECIPES, EPICURIOUS_FILE, INDIAN_FILE, OPENFOODFACTS_FILE
from etl.transformers.nutrient_normalizer import compute_normalization_cache


ALL_DATASETS = ["usda", "foodcom", "epicurious", "indian", "off"]


def run(datasets: list[str]) -> None:
    engine = create_engine(DB_URL, echo=False, pool_pre_ping=True)

    # Test connection
    try:
        with engine.connect() as c:
            c.execute(text("SELECT 1"))
        print("âœ“ Database connection OK")
    except Exception as e:
        print(f"âœ— Cannot connect to database: {e}")
        print("  Ensure MySQL is running and schema is initialised:")
        print("  mysql -u root -p < data/sql/01_schema.sql")
        print("  mysql -u root -p moodmeal < data/sql/02_seed_categories.sql")
        sys.exit(1)

    total = 0

    if "usda" in datasets:
        if USDA_FILE.exists():
            from etl.loaders.load_usda import load
            n = load(engine, str(USDA_FILE))
            total += n
        else:
            print(f"  WARNING: USDA file not found at {USDA_FILE}")

    if "foodcom" in datasets:
        if FOODCOM_RECIPES.exists():
            from etl.loaders.load_foodcom import load
            n = load(engine, str(FOODCOM_RECIPES))
            total += n
        else:
            print(f"  WARNING: Food.com file not found at {FOODCOM_RECIPES}")

    if "epicurious" in datasets:
        if EPICURIOUS_FILE.exists():
            from etl.loaders.load_epicurious import load
            n = load(engine, str(EPICURIOUS_FILE))
            total += n
        else:
            print(f"  WARNING: Epicurious file not found at {EPICURIOUS_FILE}")

    if "indian" in datasets:
        if INDIAN_FILE.exists():
            from etl.loaders.load_indian import load
            n = load(engine, str(INDIAN_FILE))
            total += n
        else:
            print(f"  WARNING: Indian food file not found at {INDIAN_FILE}")

    if "off" in datasets:
        if OPENFOODFACTS_FILE.exists():
            from etl.loaders.load_openfoodfacts import load
            n = load(engine, str(OPENFOODFACTS_FILE))
            total += n
        else:
            print(f"  WARNING: Open Food Facts file not found at {OPENFOODFACTS_FILE}")

    # Normalization cache
    print("\nComputing normalization cache...")
    n_cache = compute_normalization_cache(engine)
    print(f"âœ“ Normalization cache: {n_cache} rows updated.")

    # Validation summary
    print("\nâ”€â”€ Validation â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€")
    with engine.connect() as conn:
        r = conn.execute(text(
            "SELECT source_dataset, meal_type, COUNT(*) AS n "
            "FROM foods GROUP BY source_dataset, meal_type ORDER BY source_dataset"
        ))
        for row in r:
            print(f"  {row.source_dataset:20s} {row.meal_type:15s} {row.n:>8,d}")

        r2 = conn.execute(text(
            "SELECT COUNT(*) AS n FROM foods WHERE meal_type='complete_meal'"
        ))
        n_meals = r2.scalar()
        print(f"\n  Total complete_meal rows: {n_meals:,}")
        if n_meals < 10_000:
            print("  âš ï¸  Fewer than 10,000 complete meals â€” check dataset downloads.")
        else:
            print("  âœ“ Meal count target met (â‰¥10,000).")

        r3 = conn.execute(text(
            "SELECT COUNT(*) FROM food_nutrients WHERE data_completeness >= 5"
        ))
        n_complete = r3.scalar()
        print(f"  Completeness â‰¥5: {n_complete:,}")

        r4 = conn.execute(text("SELECT COUNT(*) FROM normalization_cache"))
        n_norm = r4.scalar()
        print(f"  Normalization cache rows: {n_norm}")

    print(f"\nâœ“ ETL complete. Total records inserted: {total:,}")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="MoodMeal ETL runner")
    parser.add_argument(
        "--datasets",
        type=str,
        default=",".join(ALL_DATASETS),
        help=f"Comma-separated list of datasets to load. Options: {ALL_DATASETS}",
    )
    args = parser.parse_args()
    selected = [d.strip().lower() for d in args.datasets.split(",")]
    run(selected)
