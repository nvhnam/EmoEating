"""
Post-ETL micronutrient enrichment pass for complete-meal foods.

For each complete-meal food with NULL zone-priority micronutrients, this script
estimates missing values by fuzzy-matching the dish name against USDA SR-28
ingredient entries already loaded in the moodmeal DB, then backfills only the
NULL columns (never overwrites source-dataset values).

Methodology:
    Uses RapidFuzz token_set_ratio (identical to load_indian.py). The dish
    name is matched against USDA ingredient names with a configurable threshold.
    When no match clears the threshold, the food remains NULL and is excluded
    under NUTRIENT_NULL=False (scientifically conservative).

Zone-priority columns targeted (union across all 4 zones):
    Q1_POS_ACT  : vitamin_c_mg, vitamin_e_mg
    Q2_NEG_ACT  : magnesium_mg, vitamin_b6_mg, vitamin_c_mg
    Q3_NEG_DEACT: folate_mcg, vitamin_b12_mcg, vitamin_d_mcg, omega3_mg
    NEUTRAL     : fiber_g, omega3_mg

Usage:
    python scripts/enrich_micronutrients.py [--dry-run] [--threshold 70] [--batch 500]

Run AFTER the main ETL pipeline (USDA must be loaded first).
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT / "app"))
sys.path.insert(0, str(PROJECT_ROOT))

import pandas as pd
from sqlalchemy import create_engine, text
from tqdm import tqdm


# Union of all zone-priority micronutrients across the 4 zones (config.py §Stage 5)
ZONE_PRIORITY_COLS: list[str] = [
    "vitamin_c_mg",     # Q1, Q2
    "vitamin_e_mg",     # Q1
    "magnesium_mg",     # Q2
    "vitamin_b6_mg",    # Q2
    "folate_mcg",       # Q3
    "vitamin_b12_mcg",  # Q3
    "vitamin_d_mcg",    # Q3
    "omega3_mg",        # Q3, NEUTRAL
    "fiber_g",          # NEUTRAL
]

# 13-field completeness definition — must match ETL loaders exactly
MOOD_RELEVANT: list[str] = [
    "tryptophan_mg", "omega3_mg", "complex_carbs_g", "magnesium_mg",
    "iron_mg", "vitamin_b12_mcg", "folate_mcg", "vitamin_c_mg",
    "vitamin_e_mg", "sugar_g", "protein_g", "fiber_g", "calories_kcal",
]

# Zone-eligibility checks used in the final report
_ZONE_CONDITIONS: dict[str, str] = {
    "Q1_POS_ACT   (vitamin_c + vitamin_e)": (
        "vitamin_c_mg IS NOT NULL AND vitamin_e_mg IS NOT NULL"
    ),
    "Q2_NEG_ACT   (magnesium + b6 + vitamin_c)": (
        "magnesium_mg IS NOT NULL AND vitamin_b6_mg IS NOT NULL AND vitamin_c_mg IS NOT NULL"
    ),
    "Q3_NEG_DEACT (folate + b12 + vitd + omega3)": (
        "folate_mcg IS NOT NULL AND vitamin_b12_mcg IS NOT NULL"
        " AND vitamin_d_mcg IS NOT NULL AND omega3_mg IS NOT NULL"
    ),
    "NEUTRAL      (fiber + omega3)": (
        "fiber_g IS NOT NULL AND omega3_mg IS NOT NULL"
    ),
}


def _load_usda_reference(engine) -> pd.DataFrame:
    """Load USDA SR-28 ingredient nutrient vectors into memory for matching."""
    cols = ", ".join(f"n.{c}" for c in ZONE_PRIORITY_COLS)
    with engine.connect() as conn:
        result = conn.execute(text(f"""
            SELECT f.name, {cols}
            FROM foods f
            JOIN food_nutrients n ON f.id = n.food_id
            WHERE f.meal_type = 'ingredient'
              AND f.source_dataset = 'usda'
        """))
        df = pd.DataFrame([dict(r._mapping) for r in result])
    if df.empty:
        print("  WARNING: No USDA ingredient rows found. Load the USDA dataset first.")
    else:
        print(f"  {len(df):,} USDA ingredient entries loaded as reference.")
    return df


def _fuzzy_match_nutrients(
    name: str,
    usda_df: pd.DataFrame,
    usda_names_lower: list[str],
    threshold: int,
) -> dict | None:
    """
    Fuzzy-match `name` against USDA ingredient names.
    Returns a dict of {col: value} for zone-priority columns, or None if no match.
    """
    from rapidfuzz import process, fuzz

    match = process.extractOne(
        name.lower(),
        usda_names_lower,
        scorer=fuzz.token_set_ratio,
        score_cutoff=threshold,
    )
    if match is None:
        return None

    idx = usda_names_lower.index(match[0])
    row = usda_df.iloc[idx]
    return {
        col: (None if pd.isna(row[col]) else float(row[col]))
        for col in ZONE_PRIORITY_COLS
    }


def _fetch_candidate_foods(engine) -> list[dict]:
    """
    Fetch complete-meal foods that have at least one NULL zone-priority column.
    Also includes all MOOD_RELEVANT columns for completeness recomputation.
    """
    null_check = " OR ".join(f"n.{c} IS NULL" for c in ZONE_PRIORITY_COLS)
    zone_select = ", ".join(f"n.{c}" for c in ZONE_PRIORITY_COLS)
    mood_extra = [c for c in MOOD_RELEVANT if c not in ZONE_PRIORITY_COLS]
    mood_select = ", ".join(f"n.{c}" for c in mood_extra)

    with engine.connect() as conn:
        result = conn.execute(text(f"""
            SELECT f.id AS food_id, f.name, f.source_dataset,
                   {zone_select}, {mood_select},
                   n.data_completeness
            FROM foods f
            JOIN food_nutrients n ON f.id = n.food_id
            WHERE f.meal_type IN ('complete_meal', 'snack')
              AND ({null_check})
            ORDER BY f.source_dataset, f.id
        """))
        return [dict(r._mapping) for r in result]


def run(dry_run: bool, threshold: int, batch_size: int) -> None:
    try:
        from rapidfuzz import fuzz  # noqa: F401
    except ImportError:
        print("ERROR: rapidfuzz is required. Install it with: pip install rapidfuzz")
        sys.exit(1)

    from etl.config import DB_URL

    engine = create_engine(DB_URL, echo=False, pool_pre_ping=True)

    try:
        with engine.connect() as c:
            c.execute(text("SELECT 1"))
        print("✓ Database connection OK")
    except Exception as exc:
        print(f"✗ Cannot connect to database: {exc}")
        sys.exit(1)

    print("\nLoading USDA SR-28 reference nutrients...")
    usda_df = _load_usda_reference(engine)
    if usda_df.empty:
        sys.exit(1)
    usda_names_lower = usda_df["name"].str.lower().tolist()

    print("\nFetching complete-meal foods with NULL zone-priority micronutrients...")
    foods = _fetch_candidate_foods(engine)
    print(f"  {len(foods):,} foods to process.")

    if not foods:
        print("Nothing to enrich — all complete-meal foods already have zone-priority data.")
        _print_zone_report(engine)
        return

    updated_count = 0
    no_match_count = 0
    zero_new_cols = 0
    batch: list[tuple[str, dict]] = []

    mode_label = "[DRY RUN] " if dry_run else ""

    with engine.connect() as conn:
        for food in tqdm(foods, desc=f"{mode_label}Enriching"):
            nutrients = _fuzzy_match_nutrients(
                food["name"], usda_df, usda_names_lower, threshold
            )
            if nutrients is None:
                no_match_count += 1
                continue

            # Only patch columns that are currently NULL in the DB
            update_fields: dict[str, float] = {}
            for col in ZONE_PRIORITY_COLS:
                if food.get(col) is None and nutrients.get(col) is not None:
                    update_fields[col] = nutrients[col]

            if not update_fields:
                zero_new_cols += 1
                continue

            # Recompute data_completeness with patched values merged in
            merged = dict(food)
            merged.update(update_fields)
            new_completeness = sum(
                1 for k in MOOD_RELEVANT if merged.get(k) is not None
            )

            set_clause = (
                ", ".join(f"{c} = :{c}" for c in update_fields)
                + ", data_completeness = :data_completeness"
            )
            params: dict = {
                **update_fields,
                "data_completeness": new_completeness,
                "food_id": food["food_id"],
            }

            if dry_run:
                tqdm.write(
                    f"  {food['source_dataset']:12s} | {food['name'][:55]:55s} | "
                    f"+{list(update_fields.keys())} | "
                    f"completeness {food['data_completeness']}→{new_completeness}"
                )
            else:
                batch.append(
                    (f"UPDATE food_nutrients SET {set_clause} WHERE food_id = :food_id", params)
                )

            updated_count += 1

            if not dry_run and len(batch) >= batch_size:
                for sql, p in batch:
                    conn.execute(text(sql), p)
                conn.commit()
                batch.clear()

        if not dry_run and batch:
            for sql, p in batch:
                conn.execute(text(sql), p)
            conn.commit()

    print(f"\n{'─'*55}")
    print(f"{mode_label}Enrichment complete")
    print(f"  Foods updated:                {updated_count:,}")
    print(f"  No USDA match (below threshold): {no_match_count:,}")
    print(f"  Match found, no new columns:  {zero_new_cols:,}")
    print(f"  Total processed:              {len(foods):,}")

    if not dry_run and updated_count > 0:
        print("\nRecomputing normalization cache...")
        from etl.transformers.nutrient_normalizer import compute_normalization_cache
        n_norm = compute_normalization_cache(engine)
        print(f"✓ Normalization cache: {n_norm} rows updated.")
        _print_zone_report(engine)


def _print_zone_report(engine) -> None:
    print("\n── Zone-ready complete-meals (NUTRIENT_NULL=False eligible) ──")
    with engine.connect() as conn:
        for zone_label, cond in _ZONE_CONDITIONS.items():
            r = conn.execute(text(f"""
                SELECT COUNT(*) FROM meals_with_nutrients
                WHERE meal_type = 'complete_meal'
                  AND data_completeness >= 5
                  AND {cond}
            """))
            n = r.scalar()
            print(f"  {zone_label}: {n:,}")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        description="EmoEating post-ETL micronutrient enrichment"
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Preview updates without writing to the DB",
    )
    parser.add_argument(
        "--threshold",
        type=int,
        default=70,
        help="RapidFuzz token_set_ratio cutoff 0–100 (default: 70)",
    )
    parser.add_argument(
        "--batch",
        type=int,
        default=500,
        help="Number of UPDATEs per DB commit (default: 500)",
    )
    args = parser.parse_args()
    run(dry_run=args.dry_run, threshold=args.threshold, batch_size=args.batch)
