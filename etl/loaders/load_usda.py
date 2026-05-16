"""
ETL loader â€” Dataset A: USDA Nutritional Values
Source: trolukovich/nutritional-values-for-common-foods-and-products
File: data/raw/nutrition.csv (~8,789 foods)

meal_type = 'ingredient'
"""

from __future__ import annotations

import pandas as pd
import numpy as np
from sqlalchemy import text
from tqdm import tqdm
import sys, os
sys.path.insert(0, str(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))))

from etl.transformers.recipe_parser import estimate_tryptophan
from etl.transformers.tag_classifier import DEFAULT as DEFAULT_CAT


COLUMN_MAP = {
    # actual column names in trolukovich/nutritional-values-for-common-foods-and-products
    "name":               "name",
    "calories":           "calories_kcal",
    "protein":            "protein_g",       # singular in this CSV
    "carbohydrate":       "carbohydrate_g",
    "fiber":              "fiber_g",
    "sugars":             "sugar_g",
    "total_fat":          "fat_g",
    "saturated_fat":      "saturated_fat_g",
    "cholesterol":        "cholesterol_mg",
    "sodium":             "sodium_mg",
    "potassium":          "potassium_mg",
    "magnesium":          "magnesium_mg",
    "calcium":            "calcium_mg",
    "irom":               "iron_mg",         # typo in source CSV
    "zink":               "zinc_mg",         # typo in source CSV
    "vitamin_a_rae":      "vitamin_a_mcg",
    "vitamin_c":          "vitamin_c_mg",
    "vitamin_e":          "vitamin_e_mg",
    "vitamin_b12":        "vitamin_b12_mcg",
    "folic_acid":         "folate_mcg",
    "tryptophan":         "tryptophan_mg",   # real column — no estimation needed
    "vitamin_b6":         "vitamin_b6_mg",
    "vitamin_d":          "vitamin_d_mcg",
}

MOOD_RELEVANT = [
    "tryptophan_mg", "omega3_mg", "complex_carbs_g", "magnesium_mg",
    "iron_mg", "vitamin_b12_mcg", "folate_mcg", "vitamin_c_mg",
    "vitamin_e_mg", "vitamin_b6_mg", "vitamin_d_mcg",
    "sugar_g", "protein_g", "fiber_g", "calories_kcal",
]


def load(engine, filepath: str, batch_size: int = 500) -> int:
    df = pd.read_csv(filepath, low_memory=False)
    df.columns = df.columns.str.lower().str.strip().str.replace(" ", "_")

    rename = {k: v for k, v in COLUMN_MAP.items() if k in df.columns}
    df = df.rename(columns=rename)

    # Strip unit suffixes like "0.26 g" → "0.26" before numeric coercion
    def strip_units(series):
        if series.dtype == object:
            return series.str.extract(r"([\d.]+)", expand=False)
        return series

    all_numeric = [
        "calories_kcal", "protein_g", "carbohydrate_g", "fiber_g", "sugar_g",
        "fat_g", "saturated_fat_g", "cholesterol_mg", "sodium_mg", "potassium_mg",
        "magnesium_mg", "calcium_mg", "iron_mg", "zinc_mg", "vitamin_a_mcg",
        "vitamin_c_mg", "vitamin_e_mg", "vitamin_b12_mcg", "folate_mcg",
        "tryptophan_mg", "vitamin_b6_mg", "vitamin_d_mcg",
    ]
    for col in all_numeric:
        if col in df.columns:
            df[col] = pd.to_numeric(strip_units(df[col]), errors="coerce")

    # Derived fields
    if "carbohydrate_g" in df.columns and "sugar_g" in df.columns:
        df["complex_carbs_g"] = (df["carbohydrate_g"].fillna(0) - df["sugar_g"].fillna(0)).clip(lower=0)
    else:
        df["complex_carbs_g"] = None

    # tryptophan is in grams in this CSV → convert to mg
    if "tryptophan_mg" in df.columns:
        df["tryptophan_mg"] = df["tryptophan_mg"] * 1000
    else:
        df["tryptophan_mg"] = df["protein_g"].apply(
            lambda p: estimate_tryptophan(float(p)) if pd.notna(p) else None
        )
    df["omega3_mg"] = None  # not in this dataset

    # Filter
    df = df[df["name"].notna()]
    if "calories_kcal" in df.columns:
        df = df[df["calories_kcal"].fillna(0) > 0]

    df["data_completeness"] = df[MOOD_RELEVANT].apply(
        lambda row: row.notna().sum(), axis=1
    ).astype(int)

    inserted = 0
    with engine.connect() as conn:
        for _, row in tqdm(df.iterrows(), total=len(df), desc="USDA"):
            name = str(row["name"])[:255]
            try:
                r = conn.execute(text("""
                    INSERT INTO foods (name, category_id, meal_type, source_dataset)
                    VALUES (:name, :cat, 'ingredient', 'usda')
                """), {"name": name, "cat": DEFAULT_CAT[0]})
                food_id = r.lastrowid

                nutrient_vals = {k: _safe(row, k) for k in [
                    "calories_kcal","protein_g","carbohydrate_g","complex_carbs_g",
                    "fiber_g","sugar_g","fat_g","saturated_fat_g",
                    "tryptophan_mg","omega3_mg","magnesium_mg","iron_mg",
                    "vitamin_b12_mcg","folate_mcg","vitamin_c_mg","vitamin_e_mg",
                    "vitamin_b6_mg","vitamin_d_mcg",
                    "vitamin_a_mcg","calcium_mg","zinc_mg","potassium_mg",
                    "sodium_mg","cholesterol_mg",
                ]}
                nutrient_vals["food_id"] = food_id
                nutrient_vals["data_completeness"] = int(row.get("data_completeness", 0))

                conn.execute(text("""
                    INSERT INTO food_nutrients
                    (food_id, calories_kcal, protein_g, carbohydrate_g, complex_carbs_g,
                     fiber_g, sugar_g, fat_g, saturated_fat_g,
                     tryptophan_mg, omega3_mg, magnesium_mg, iron_mg,
                     vitamin_b12_mcg, folate_mcg, vitamin_c_mg, vitamin_e_mg,
                     vitamin_b6_mg, vitamin_d_mcg,
                     vitamin_a_mcg, calcium_mg, zinc_mg, potassium_mg,
                     sodium_mg, cholesterol_mg, data_completeness)
                    VALUES
                    (:food_id, :calories_kcal, :protein_g, :carbohydrate_g, :complex_carbs_g,
                     :fiber_g, :sugar_g, :fat_g, :saturated_fat_g,
                     :tryptophan_mg, :omega3_mg, :magnesium_mg, :iron_mg,
                     :vitamin_b12_mcg, :folate_mcg, :vitamin_c_mg, :vitamin_e_mg,
                     :vitamin_b6_mg, :vitamin_d_mcg,
                     :vitamin_a_mcg, :calcium_mg, :zinc_mg, :potassium_mg,
                     :sodium_mg, :cholesterol_mg, :data_completeness)
                """), nutrient_vals)
                inserted += 1

                if inserted % batch_size == 0:
                    conn.commit()

            except Exception as e:
                print(f"  USDA row error ({name}): {e}")
                continue

        conn.commit()

    print(f"USDA: inserted {inserted} ingredient records.")
    return inserted


def _safe(row, key):
    try:
        val = row[key]
        if pd.isna(val):
            return None
        return float(val)
    except Exception:
        return None
