"""
ETL loader â€” Dataset D: Indian Food Dataset
Source: nehaprabhavalkar/indian-food-dataset
File: data/raw/indian_food.csv

No direct nutritional data â€” estimates nutrients via fuzzy ingredient matching
against the USDA food_nutrients table already loaded.
"""

from __future__ import annotations

import pandas as pd
import numpy as np
from sqlalchemy import text
from tqdm import tqdm
import sys, os
sys.path.insert(0, str(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))))

from etl.transformers.tag_classifier import indian_course_to_category

MOOD_RELEVANT = [
    "tryptophan_mg", "omega3_mg", "complex_carbs_g", "magnesium_mg",
    "iron_mg", "vitamin_b12_mcg", "folate_mcg", "vitamin_c_mg",
    "vitamin_e_mg", "sugar_g", "protein_g", "fiber_g", "calories_kcal",
]

NUTRIENT_COLS = [
    "calories_kcal","protein_g","carbohydrate_g","complex_carbs_g",
    "fiber_g","sugar_g","fat_g","saturated_fat_g",
    "tryptophan_mg","omega3_mg","magnesium_mg","iron_mg",
    "vitamin_b12_mcg","folate_mcg","vitamin_c_mg","vitamin_e_mg",
    "vitamin_a_mcg","calcium_mg","zinc_mg","potassium_mg",
    "sodium_mg","cholesterol_mg",
]


def _fetch_usda_nutrients(engine) -> pd.DataFrame:
    """Load USDA ingredient nutrients into memory for fuzzy matching."""
    with engine.connect() as conn:
        result = conn.execute(text("""
            SELECT f.name, n.calories_kcal, n.protein_g, n.carbohydrate_g,
                   n.complex_carbs_g, n.fiber_g, n.sugar_g, n.fat_g,
                   n.saturated_fat_g, n.tryptophan_mg, n.omega3_mg,
                   n.magnesium_mg, n.iron_mg, n.vitamin_b12_mcg,
                   n.folate_mcg, n.vitamin_c_mg, n.vitamin_e_mg,
                   n.vitamin_a_mcg, n.calcium_mg, n.zinc_mg,
                   n.potassium_mg, n.sodium_mg, n.cholesterol_mg
            FROM foods f
            JOIN food_nutrients n ON f.id = n.food_id
            WHERE f.meal_type = 'ingredient'
        """))
        df = pd.DataFrame([dict(r._mapping) for r in result])
    return df


def _estimate_nutrients(ingredients_str: str, usda_df: pd.DataFrame) -> dict:
    """
    Fuzzy-match each ingredient to USDA table and average the nutrient values.
    Returns dict of averaged nutrient values.
    """
    try:
        from rapidfuzz import process, fuzz
    except ImportError:
        return {}

    if not ingredients_str or pd.isna(ingredients_str):
        return {}

    ingredients = [i.strip().lower() for i in str(ingredients_str).split(",")]
    usda_names = usda_df["name"].str.lower().tolist()

    matched_rows = []
    for ing in ingredients:
        match = process.extractOne(ing, usda_names, scorer=fuzz.token_set_ratio, score_cutoff=70)
        if match:
            idx = usda_names.index(match[0])
            matched_rows.append(usda_df.iloc[idx])

    if not matched_rows:
        return {}

    avg = pd.DataFrame(matched_rows)[NUTRIENT_COLS].mean(skipna=True)
    return {k: (None if pd.isna(v) else float(v)) for k, v in avg.items()}


def load(engine, filepath: str, batch_size: int = 100) -> int:
    df = pd.read_csv(filepath, low_memory=False)

    print("Loading USDA reference data for ingredient matching...")
    usda_df = _fetch_usda_nutrients(engine)
    if usda_df.empty:
        print("  WARNING: USDA data not found. Load USDA first. Skipping Indian dataset.")
        return 0

    inserted = 0
    with engine.connect() as conn:
        for _, row in tqdm(df.iterrows(), total=len(df), desc="Indian Food"):
            try:
                name = str(row.get("name", ""))[:255].strip()
                if not name:
                    continue

                course = str(row.get("course", ""))
                cat_id, meal_type = indian_course_to_category(course)

                diet = str(row.get("diet", "")).lower()
                is_veg   = "vegetarian" in diet
                is_vegan = "vegan" in diet

                prep = _to_int(row.get("prep_time"))
                cook = _to_int(row.get("cook_time"))

                r = conn.execute(text("""
                    INSERT INTO foods
                    (name, category_id, meal_type, source_dataset, cuisine,
                     prep_time_min, cook_time_min, is_vegetarian, is_vegan)
                    VALUES (:name, :cat, :meal_type, 'indian', 'Indian',
                            :prep, :cook, :veg, :vegan)
                """), {
                    "name": name, "cat": cat_id, "meal_type": meal_type,
                    "prep": prep, "cook": cook,
                    "veg": int(is_veg), "vegan": int(is_vegan),
                })
                food_id = r.lastrowid

                # Estimate nutrients from ingredients
                nutrients = _estimate_nutrients(row.get("ingredients", ""), usda_df)

                completeness = sum(1 for k in MOOD_RELEVANT if nutrients.get(k) is not None)
                nv = {k: nutrients.get(k) for k in NUTRIENT_COLS}
                nv["food_id"] = food_id
                nv["data_completeness"] = completeness

                conn.execute(text("""
                    INSERT INTO food_nutrients
                    (food_id, calories_kcal, protein_g, carbohydrate_g, complex_carbs_g,
                     fiber_g, sugar_g, fat_g, saturated_fat_g,
                     tryptophan_mg, omega3_mg, magnesium_mg, iron_mg,
                     vitamin_b12_mcg, folate_mcg, vitamin_c_mg, vitamin_e_mg,
                     vitamin_a_mcg, calcium_mg, zinc_mg, potassium_mg,
                     sodium_mg, cholesterol_mg, data_completeness)
                    VALUES
                    (:food_id, :calories_kcal, :protein_g, :carbohydrate_g, :complex_carbs_g,
                     :fiber_g, :sugar_g, :fat_g, :saturated_fat_g,
                     :tryptophan_mg, :omega3_mg, :magnesium_mg, :iron_mg,
                     :vitamin_b12_mcg, :folate_mcg, :vitamin_c_mg, :vitamin_e_mg,
                     :vitamin_a_mcg, :calcium_mg, :zinc_mg, :potassium_mg,
                     :sodium_mg, :cholesterol_mg, :data_completeness)
                """), nv)

                # Insert ingredients
                for ing in [i.strip() for i in str(row.get("ingredients", "")).split(",") if i.strip()]:
                    conn.execute(text("""
                        INSERT INTO food_ingredients (meal_id, ingredient_name)
                        VALUES (:mid, :ing)
                    """), {"mid": food_id, "ing": ing[:200]})

                inserted += 1
                if inserted % batch_size == 0:
                    conn.commit()

            except Exception as e:
                print(f"  Indian row error: {e}")
                continue

        conn.commit()

    print(f"Indian Food: inserted {inserted} records.")
    return inserted


def _to_int(val):
    try:
        return int(float(val))
    except Exception:
        return None
