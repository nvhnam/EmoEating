"""
ETL loader â€” Dataset E: Epicurious Recipes
Source: hugodarwood/epicurious-recipes-with-rating-and-nutrition
File: data/raw/epi_r.csv (~20,000 recipes)

protein/fat are grams per serving; normalise assuming average serving = 250g.
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

ASSUMED_SERVING_G = 250.0

MOOD_RELEVANT = [
    "tryptophan_mg", "omega3_mg", "complex_carbs_g", "magnesium_mg",
    "iron_mg", "vitamin_b12_mcg", "folate_mcg", "vitamin_c_mg",
    "vitamin_e_mg", "sugar_g", "protein_g", "fiber_g", "calories_kcal",
]

CATEGORY_BOOL_COLS = [
    "alcoholic", "appetizer", "backyard bbq", "barbecue", "bean", "beef",
    "birthday", "bread", "breakfast", "brunch", "cake", "chicken", "cocktail",
    "cookies", "dairy free", "dessert", "dinner", "duck", "egg", "fall",
    "fish", "gluten-free", "healthy", "high fiber", "high in protein",
    "kid-friendly", "lamb", "leafy green", "low cal", "low cholesterol",
    "low fat", "low sodium", "low sugar", "lunch", "main dish", "meatless",
    "mushroom", "no cook", "no sugar added", "non-alcoholic", "one-pot meal",
    "pasta", "peanut free", "pork", "potato", "quick & easy", "salad",
    "sandwich", "sauce", "sautÃ©", "seafood", "snack", "soup/stew",
    "sugar conscious", "tofu", "tomato", "tree nut free", "turkey",
    "vegan", "vegetarian", "wheat/gluten-free",
]


def load(engine, filepath: str, batch_size: int = 200) -> int:
    df = pd.read_csv(filepath, low_memory=False)

    # Identify the title column
    title_col = "title" if "title" in df.columns else df.columns[0]

    inserted = 0
    with engine.connect() as conn:
        for _, row in tqdm(df.iterrows(), total=len(df), desc="Epicurious"):
            try:
                name = str(row.get(title_col, ""))[:255].strip()
                if not name:
                    continue

                kcal = _to_float(row.get("calories"))
                prot_per_serving = _to_float(row.get("protein"))
                fat_per_serving  = _to_float(row.get("fat"))
                sodium_mg        = _to_float(row.get("sodium"))
                rating           = _to_float(row.get("rating"))

                if kcal is None or kcal < 80:
                    continue

                # Normalise to per-100g
                factor = 100.0 / ASSUMED_SERVING_G
                protein_g = (prot_per_serving * factor) if prot_per_serving else None
                fat_g     = (fat_per_serving  * factor) if fat_per_serving  else None

                # Derive category from boolean columns
                active_tags = [c.lower() for c in CATEGORY_BOOL_COLS
                               if c in df.columns and str(row.get(c, 0)) in ("1", "1.0", "True")]
                cat_id, meal_type = classify_from_text(" ".join(active_tags))

                is_veg   = "vegetarian" in active_tags or "meatless" in active_tags
                is_vegan = "vegan" in active_tags
                is_gf    = any(t in active_tags for t in ["gluten-free", "wheat/gluten-free"])

                r = conn.execute(text("""
                    INSERT INTO foods
                    (name, category_id, meal_type, source_dataset,
                     rating, is_vegetarian, is_vegan, is_gluten_free)
                    VALUES (:name, :cat, :meal_type, 'epicurious',
                            :rating, :veg, :vegan, :gf)
                """), {
                    "name": name, "cat": cat_id, "meal_type": meal_type,
                    "rating": rating, "veg": int(is_veg),
                    "vegan": int(is_vegan), "gf": int(is_gf),
                })
                food_id = r.lastrowid

                trp = estimate_tryptophan(protein_g)
                nutrient_vals = {
                    "food_id":          food_id,
                    "calories_kcal":    kcal,
                    "protein_g":        protein_g,
                    "fat_g":            fat_g,
                    "sodium_mg":        sodium_mg,
                    "tryptophan_mg":    trp,
                    "carbohydrate_g":   None,
                    "complex_carbs_g":  None,
                    "fiber_g":          None,
                    "sugar_g":          None,
                    "saturated_fat_g":  None,
                    "omega3_mg":        None,
                    "magnesium_mg":     None,
                    "iron_mg":          None,
                    "vitamin_b12_mcg":  None,
                    "folate_mcg":       None,
                    "vitamin_c_mg":     None,
                    "vitamin_e_mg":     None,
                    "vitamin_a_mcg":    None,
                    "calcium_mg":       None,
                    "zinc_mg":          None,
                    "potassium_mg":     None,
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
                print(f"  Epicurious row error: {e}")
                continue

        conn.commit()

    print(f"Epicurious: inserted {inserted} records.")
    return inserted


def _to_float(val):
    try:
        f = float(val)
        return f if not (f != f) else None  # NaN check
    except Exception:
        return None
