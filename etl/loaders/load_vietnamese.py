"""
ETL loader — Vietnamese Food Nutritional Database
Source: data/raw/vietnamese_food.csv
Schema: moodmeal_vn (separate from main moodmeal schema)

All nutritional values in the CSV are per 100 g serving.
meal_type = 'complete_meal', cuisine = 'Vietnamese'
"""

from __future__ import annotations

import pandas as pd
from sqlalchemy import text
from tqdm import tqdm
import sys
import os

sys.path.insert(0, str(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))))


MOOD_RELEVANT = [
    "tryptophan_mg", "omega3_mg", "complex_carbs_g", "magnesium_mg",
    "iron_mg", "vitamin_b12_mcg", "folate_mcg", "vitamin_c_mg",
    "vitamin_e_mg", "sugar_g", "protein_g", "fiber_g", "calories_kcal",
]

# Category id → keywords to match against Food_Name_English (case-insensitive).
# Checked in order; first match wins. Default category_id = 3 (dinner).
_CAT_KEYWORDS: dict[int, list[str]] = {
    6:  ["juice", "tea", "drink", "milk", "water", "beer", "wine", "coffee", "smoothie",
         "soft drink", "soda", "syrup", "nectar"],
    9:  ["soup", "broth", "stew", "hotpot", "canh", "pho", "bun bo", "chowder", "bisque",
         "porridge", "congee", "gruel", "jook"],
    5:  ["cake", "sweet", "pudding", "candy", "chocolate", "jam", "jelly", "biscuit",
         "cookie", "dessert", "ice cream", "custard", "tart", "wafer"],
    1:  ["oatmeal", "cereal", "granola"],
    10: ["salad"],
    4:  ["snack", "chip", "cracker", "popcorn"],
    7:  ["rice", "noodle", "bread", "baguette", "pasta", "vermicelli", "dumpling"],
}


def _safe_float(val, scale: float = 1.0):
    """Return float or None; handles empty strings, 'nan', etc."""
    try:
        v = str(val).strip()
        if not v or v.lower() in ("nan", "none", "null", "-"):
            return None
        return float(v) * scale
    except (ValueError, TypeError):
        return None


def _classify_category(name_en: str) -> int:
    """Keyword-based category classifier. Returns category_id (default 3 = dinner)."""
    lower = (name_en or "").lower()
    for cat_id, keywords in _CAT_KEYWORDS.items():
        if any(kw in lower for kw in keywords):
            return cat_id
    return 3  # dinner


def load(engine, filepath: str, batch_size: int = 200) -> int:
    """
    Load vietnamese_food.csv into the connected moodmeal_vn schema.
    Returns number of rows inserted.
    """
    # Verify target schema has the foods table before starting
    try:
        with engine.connect() as check_conn:
            check_conn.execute(text("SELECT 1 FROM foods LIMIT 1"))
    except Exception:
        print(
            "\n  ERROR: moodmeal_vn schema is not initialised.\n"
            "  Run: mysql -u root -p < data/sql/vn_01_schema.sql\n"
            "       mysql -u root -p moodmeal_vn < data/sql/vn_02_seed_categories.sql\n"
        )
        return 0

    df = pd.read_csv(filepath, low_memory=False, encoding="utf-8-sig")

    # Drop completely empty rows
    df = df.dropna(how="all")

    inserted = 0
    skipped = 0

    with engine.connect() as conn:
        for _, row in tqdm(df.iterrows(), total=len(df), desc="Vietnamese"):
            name_en = str(row.get("Food_Name_English", "") or "").strip()
            name_vn = str(row.get("Food_Name_Vietnamese", "") or "").strip()

            # Use English name; fall back to Vietnamese if English is absent
            name = name_en if name_en and name_en.lower() not in ("nan", "none") else name_vn
            if not name or name.lower() in ("nan", "none"):
                skipped += 1
                continue

            calories = _safe_float(row.get("Energy_kcal"))
            if calories is None or calories <= 0:
                skipped += 1
                continue

            # --- Derived nutrients ---
            carb_g     = _safe_float(row.get("Carbohydrate_g"))
            sugar_g    = _safe_float(row.get("Sugar_total_g"))
            complex_carbs = None
            if carb_g is not None:
                complex_carbs = max(0.0, carb_g - (sugar_g or 0.0))

            epa_g = _safe_float(row.get("EPA_C20_5_n3_g"))
            dha_g = _safe_float(row.get("DHA_C22_6_n3_g"))
            omega3_sum = (epa_g or 0.0) + (dha_g or 0.0)
            omega3_mg = omega3_sum * 1000.0 if omega3_sum > 0 else None

            food_code  = str(row.get("Food_Code", "")).strip()
            category_id = _classify_category(name_en)

            try:
                r = conn.execute(text("""
                    INSERT INTO foods
                        (name, category_id, meal_type, cuisine,
                         source_dataset, source_id, serving_size_g, description)
                    VALUES
                        (:name, :cat, 'complete_meal', 'Vietnamese',
                         'vietnamese_food', :source_id, 100, :desc)
                """), {
                    "name":      name[:255],
                    "cat":       category_id,
                    "source_id": food_code or None,
                    "desc":      name_vn[:500] if name_vn and name_vn.lower() not in ("nan", "none") else None,
                })
                food_id = r.lastrowid

                nutrient_vals = {
                    "food_id":         food_id,
                    "calories_kcal":   calories,
                    "protein_g":       _safe_float(row.get("Protein_g")),
                    "carbohydrate_g":  carb_g,
                    "complex_carbs_g": complex_carbs,
                    "fiber_g":         _safe_float(row.get("Fiber_g")),
                    "sugar_g":         sugar_g,
                    "fat_g":           _safe_float(row.get("Fat_g")),
                    "saturated_fat_g": _safe_float(row.get("Total_SFA_g")),
                    # Tryptophan is already in mg in this CSV (do NOT multiply by 1000)
                    "tryptophan_mg":   _safe_float(row.get("Tryptophan_mg")),
                    "omega3_mg":       omega3_mg,
                    "magnesium_mg":    _safe_float(row.get("Magnesium_mg")),
                    "iron_mg":         _safe_float(row.get("Iron_mg")),
                    # Vitamin_B12_ug: ug == mcg, direct copy
                    "vitamin_b12_mcg": _safe_float(row.get("Vitamin_B12_ug")),
                    # Folate_ug: ug == mcg, direct copy
                    "folate_mcg":      _safe_float(row.get("Folate_ug")),
                    "vitamin_c_mg":    _safe_float(row.get("Vitamin_C_mg")),
                    "vitamin_e_mg":    _safe_float(row.get("Vitamin_E_mg")),
                    # Vitamin_A_ug: ug == mcg, direct copy
                    "vitamin_a_mcg":   _safe_float(row.get("Vitamin_A_ug")),
                    "calcium_mg":      _safe_float(row.get("Calcium_mg")),
                    "zinc_mg":         _safe_float(row.get("Zinc_mg")),
                    "potassium_mg":    _safe_float(row.get("Potassium_mg")),
                    "sodium_mg":       _safe_float(row.get("Sodium_mg")),
                    "cholesterol_mg":  _safe_float(row.get("Cholesterol_mg")),
                }

                # Count non-None mood-relevant nutrients for data_completeness
                completeness = sum(
                    1 for k in MOOD_RELEVANT if nutrient_vals.get(k) is not None
                )
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
                print(f"  Vietnamese row error ({name}): {e}")
                continue

        conn.commit()

    print(f"Vietnamese: inserted {inserted} complete_meal records ({skipped} skipped).")
    return inserted
