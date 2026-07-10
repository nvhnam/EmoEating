"""
ETL loader â€” Dataset C: Open Food Facts
Source: openfoodfacts/world.openfoodfacts.org.products
File: data/raw/en.openfoodfacts.org.products.tsv (large â€” chunked read)

Filters for US products with valid caloric data.
"""

from __future__ import annotations

import pandas as pd
import numpy as np
from sqlalchemy import text
from tqdm import tqdm
import sys, os
sys.path.insert(0, str(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))))

from etl.transformers.recipe_parser import estimate_tryptophan
from etl.transformers.tag_classifier import classify_from_text

USECOLS = [
    "product_name", "categories_en",
    "energy-kcal_100g", "proteins_100g", "carbohydrates_100g",
    "fiber_100g", "sugars_100g", "fat_100g",
    "iron_100g", "magnesium_100g",
    "vitamin-c_100g", "vitamin-e_100g", "vitamin-b12_100g",
    "omega-3-fat_100g",
]

MOOD_RELEVANT = [
    "tryptophan_mg", "omega3_mg", "complex_carbs_g", "magnesium_mg",
    "iron_mg", "vitamin_b12_mcg", "folate_mcg", "vitamin_c_mg",
    "vitamin_e_mg", "sugar_g", "protein_g", "fiber_g", "calories_kcal",
]

CHUNK_SIZE = 10_000


def load(engine, filepath: str, batch_size: int = 500, max_rows: int = 50_000) -> int:
    reader = pd.read_csv(
        filepath,
        sep="\t",
        usecols=lambda c: c in USECOLS,
        low_memory=False,
        chunksize=CHUNK_SIZE,
        on_bad_lines="skip",
    )

    inserted = 0
    rows_read = 0

    with engine.connect() as conn:
        for chunk in reader:
            if max_rows and rows_read >= max_rows:
                break

            # Filter
            chunk = chunk[chunk["product_name"].notna()]
            if "energy-kcal_100g" in chunk.columns:
                chunk = chunk[
                    pd.to_numeric(chunk["energy-kcal_100g"], errors="coerce").between(20, 900)
                ]

            for _, row in chunk.iterrows():
                if max_rows and rows_read >= max_rows:
                    break
                rows_read += 1

                try:
                    name = str(row.get("product_name", ""))[:255].strip()
                    if not name:
                        continue

                    cats = str(row.get("categories_en", ""))
                    cat_id, meal_type = classify_from_text(cats)

                    kcal    = _to_float(row.get("energy-kcal_100g"))
                    prot    = _to_float(row.get("proteins_100g"))
                    carb    = _to_float(row.get("carbohydrates_100g"))
                    fiber   = _to_float(row.get("fiber_100g"))
                    sugar   = _to_float(row.get("sugars_100g"))
                    fat     = _to_float(row.get("fat_100g"))
                    iron    = _to_float(row.get("iron_100g"))
                    mag     = _to_float(row.get("magnesium_100g"))
                    vitc    = _to_float(row.get("vitamin-c_100g"))
                    vite    = _to_float(row.get("vitamin-e_100g"))
                    vitb12  = _to_float(row.get("vitamin-b12_100g"))
                    omega3  = _to_float(row.get("omega-3-fat_100g"))

                    # Convert g to mg where needed (iron, magnesium, vitc, vite, vitb12, omega-3 are in g/100g in OFF)
                    iron   = (iron * 1000) if iron is not None else None
                    mag    = (mag  * 1000) if mag  is not None else None
                    vitc   = (vitc * 1000) if vitc is not None else None
                    vite   = (vite * 1000) if vite is not None else None
                    vitb12 = (vitb12 * 1000) if vitb12 is not None else None
                    # Cap at 99.999 g/100g before converting — values above this are
                    # erroneous in OFF and would overflow DECIMAL(8,3) (max 99999.999 mg).
                    if omega3 is not None and omega3 > 99.999:
                        omega3 = None
                    omega3 = (omega3 * 1000) if omega3 is not None else None

                    complex_carbs = max(0.0, (carb or 0) - (sugar or 0)) if carb is not None else None
                    trp = estimate_tryptophan(prot)

                    r = conn.execute(text("""
                        INSERT INTO foods (name, category_id, meal_type, source_dataset)
                        VALUES (:name, :cat, :meal_type, 'openfoodfacts')
                    """), {"name": name, "cat": cat_id, "meal_type": meal_type})
                    food_id = r.lastrowid

                    nutrient_vals = {
                        "food_id":          food_id,
                        "calories_kcal":    kcal,
                        "protein_g":        prot,
                        "carbohydrate_g":   carb,
                        "complex_carbs_g":  complex_carbs,
                        "fiber_g":          fiber,
                        "sugar_g":          sugar,
                        "fat_g":            fat,
                        "saturated_fat_g":  None,
                        "tryptophan_mg":    trp,
                        "omega3_mg":        omega3,
                        "magnesium_mg":     mag,
                        "iron_mg":          iron,
                        "vitamin_b12_mcg":  vitb12,
                        "folate_mcg":       None,
                        "vitamin_c_mg":     vitc,
                        "vitamin_e_mg":     vite,
                        "vitamin_a_mcg":    None,
                        "calcium_mg":       None,
                        "zinc_mg":          None,
                        "potassium_mg":     None,
                        "sodium_mg":        None,
                        "cholesterol_mg":   None,
                    }
                    completeness = sum(1 for k in MOOD_RELEVANT if nutrient_vals.get(k) is not None)
                    nutrient_vals["data_completeness"] = completeness

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
                    """), nutrient_vals)

                    inserted += 1
                    if inserted % batch_size == 0:
                        conn.commit()

                except Exception as e:
                    print(f"  OFF row error: {e}")
                    continue

        conn.commit()

    print(f"Open Food Facts: inserted {inserted} records (read {rows_read} rows).")
    return inserted


def _to_float(val):
    try:
        f = float(val)
        return None if (f != f) else f  # NaN â†’ None
    except Exception:
        return None
