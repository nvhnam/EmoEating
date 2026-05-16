-- Run this if moodmeal_vn was already initialised before the view was updated
-- to include the description column (needed for Vietnamese name display in UI).

USE moodmeal_vn;

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
    n.data_completeness
FROM foods f
JOIN food_categories fc ON f.category_id = fc.id
JOIN food_nutrients  n  ON f.id = n.food_id
WHERE f.meal_type IN ('complete_meal','snack','beverage');
