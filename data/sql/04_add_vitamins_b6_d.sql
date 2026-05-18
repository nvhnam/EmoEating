-- Migration: add vitamin_b6_mg and vitamin_d_mcg to food_nutrients (moodmeal)
-- Run this against an existing moodmeal DB that was built before this migration.
-- Safe to run multiple times — MySQL silently errors if columns already exist.

USE moodmeal;

ALTER TABLE food_nutrients
    ADD COLUMN IF NOT EXISTS vitamin_b6_mg DECIMAL(6,3) NULL AFTER vitamin_e_mg,
    ADD COLUMN IF NOT EXISTS vitamin_d_mcg DECIMAL(6,3) NULL AFTER vitamin_b6_mg;

-- Refresh the view to include fat_g, vitamin_b6_mg, vitamin_d_mcg
CREATE OR REPLACE VIEW meals_with_nutrients AS
SELECT
    f.id,
    f.name,
    f.description,
    f.image_url,
    fc.name          AS category,
    f.meal_type,
    f.cuisine,
    f.is_vegetarian,
    f.is_vegan,
    f.is_gluten_free,
    f.is_dairy_free,
    f.rating,
    f.prep_time_min,
    f.cook_time_min,
    f.serving_size_g,
    n.calories_kcal,
    n.protein_g,
    n.carbohydrate_g,
    n.fat_g,
    n.complex_carbs_g,
    n.fiber_g,
    n.sugar_g,
    n.tryptophan_mg,
    n.omega3_mg,
    n.magnesium_mg,
    n.iron_mg,
    n.vitamin_b12_mcg,
    n.folate_mcg,
    n.vitamin_c_mg,
    n.vitamin_e_mg,
    n.vitamin_b6_mg,
    n.vitamin_d_mcg,
    n.data_completeness
FROM foods f
JOIN food_categories fc ON f.category_id = fc.id
JOIN food_nutrients  n  ON f.id = n.food_id
WHERE f.meal_type IN ('complete_meal','snack','beverage');
