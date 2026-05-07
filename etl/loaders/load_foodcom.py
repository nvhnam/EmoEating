"""
ETL loader â€” Dataset B: Food.com Recipes (PRIMARY MEAL SOURCE)
Source: shuyangli94/food-com-recipes-and-user-interactions
File: data/raw/RAW_recipes.csv (~231,637 recipes)

Nutrition column is PDV format; see recipe_parser.py for conversion.
meal_type = 'complete_meal'
"""

from __future__ import annotations

import pandas as pd
import numpy as np
from sqlalchemy import text
from tqdm import tqdm
import sys, os
sys.path.insert(0, str(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))))

from etl.transformers.recipe_parser import (
    parse_foodcom_nutrition, parse_list_column, estimate_tryptophan
)
from etl.transformers.tag_classifier import classify_from_tags

MOOD_RELEVANT = [
    "tryptophan_mg", "omega3_mg", "complex_carbs_g", "magnesium_mg",
    "iron_mg", "vitamin_b12_mcg", "folate_mcg", "vitamin_c_mg",
    "vitamin_e_mg", "sugar_g", "protein_g", "fiber_g", "calories_kcal",
]

VEGETARIAN_TAGS = {"vegetarian", "vegan"}
VEGAN_TAGS      = {"vegan"}
GF_TAGS         = {"gluten-free", "gluten free"}


def load(engine, filepath: str, batch_size: int = 200, max_rows: int = None) -> int:
    df = pd.read_csv(filepath, low_memory=False)
    if max_rows:
        df = df.head(max_rows)

    # Filter by time
    df["minutes"] = pd.to_numeric(df["minutes"], errors="coerce")
    df = df[df["minutes"] < 120].copy()

    inserted = 0
    with engine.connect() as conn:
        for _, row in tqdm(df.iterrows(), total=len(df), desc="Food.com"):
            try:
                nutrition = parse_foodcom_nutrition(row.get("nutrition", "[]"))
                if not nutrition or nutrition.get("calories_kcal", 0) < 80:
                    continue
                if all(nutrition.get(k) is None for k in ["protein_g", "carbohydrate_g", "fat_g"]):
                    continue

                tags_list = parse_list_column(row.get("tags", "[]"))
                tags_lower = [t.lower() for t in tags_list]
                cat_id, meal_type = classify_from_tags(tags_lower)

                is_veg   = any(t in tags_lower for t in VEGETARIAN_TAGS)
                is_vegan = any(t in tags_lower for t in VEGAN_TAGS)
                is_gf    = any(t in tags_lower for t in GF_TAGS)

                prep_time = min(int(row.get("minutes", 60)), 240)
                name = str(row.get("name", ""))[:255]
                source_id = str(row.get("id", ""))[:100]

                r = conn.execute(text("""
                    INSERT INTO foods
                    (name, category_id, meal_type, source_dataset, source_id,
                     prep_time_min, is_vegetarian, is_vegan, is_gluten_free)
                    VALUES (:name, :cat, :meal_type, 'foodcom', :src_id,
                            :prep, :veg, :vegan, :gf)
                """), {
                    "name": name, "cat": cat_id, "meal_type": meal_type,
                    "src_id": source_id, "prep": prep_time,
                    "veg": int(is_veg), "vegan": int(is_vegan), "gf": int(is_gf),
                })
                food_id = r.lastrowid

                # Compute derived nutrients
                protein_g = nutrition.get("protein_g")
                carb_g    = nutrition.get("carbohydrate_g")
                sugar_g   = nutrition.get("sugar_g")
                complex_carbs = max(0.0, (carb_g or 0) - (sugar_g or 0))
                trp = estimate_tryptophan(protein_g)

                nutrient_vals = {
                    "food_id":          food_id,
                    "calories_kcal":    nutrition.get("calories_kcal"),
                    "protein_g":        protein_g,
                    "carbohydrate_g":   carb_g,
                    "complex_carbs_g":  complex_carbs if carb_g is not None else None,
                    "fiber_g":          None,
                    "sugar_g":          sugar_g,
                    "fat_g":            nutrition.get("fat_g"),
                    "saturated_fat_g":  nutrition.get("saturated_fat_g"),
                    "sodium_mg":        nutrition.get("sodium_mg"),
                    "tryptophan_mg":    trp,
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

                # Count data completeness
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

                # Insert ingredients
                ingredients = parse_list_column(row.get("ingredients", "[]"))
                for ing in ingredients[:30]:  # cap at 30 per recipe
                    conn.execute(text("""
                        INSERT INTO food_ingredients (meal_id, ingredient_name)
                        VALUES (:mid, :ing)
                    """), {"mid": food_id, "ing": str(ing)[:200]})

                inserted += 1
                if inserted % batch_size == 0:
                    conn.commit()

            except Exception as e:
                print(f"  FoodCom row error: {e}")
                continue

        conn.commit()

    print(f"Food.com: inserted {inserted} recipe records.")
    return inserted
