-- Compute normalization cache (min/max per ENMS-relevant nutrient).
-- Run AFTER ETL to populate normalization_cache.
-- The ETL runner (etl/run_etl.py) calls this automatically via Python
-- (etl/transformers/nutrient_normalizer.py). Only run this SQL manually
-- if you need to refresh the cache without re-running the full ETL.
--
-- Covers all 15 nutrients tracked in ENMS scoring and data_completeness:
--   macros:      complex_carbs_g, protein_g, fiber_g, sugar_g, calories_kcal
--   ENMS micros: omega3_mg, magnesium_mg, vitamin_b6_mg, vitamin_c_mg,
--                vitamin_e_mg, folate_mcg, vitamin_b12_mcg, vitamin_d_mcg,
--                iron_mg, tryptophan_mg

USE moodmeal;

INSERT INTO normalization_cache (nutrient_key, min_value, max_value)
SELECT 'tryptophan_mg',   MIN(tryptophan_mg),   MAX(tryptophan_mg)   FROM food_nutrients WHERE tryptophan_mg   IS NOT NULL
UNION ALL
SELECT 'omega3_mg',       MIN(omega3_mg),       MAX(omega3_mg)       FROM food_nutrients WHERE omega3_mg       IS NOT NULL
UNION ALL
SELECT 'complex_carbs_g', MIN(complex_carbs_g), MAX(complex_carbs_g) FROM food_nutrients WHERE complex_carbs_g IS NOT NULL
UNION ALL
SELECT 'magnesium_mg',    MIN(magnesium_mg),    MAX(magnesium_mg)    FROM food_nutrients WHERE magnesium_mg    IS NOT NULL
UNION ALL
SELECT 'iron_mg',         MIN(iron_mg),         MAX(iron_mg)         FROM food_nutrients WHERE iron_mg         IS NOT NULL
UNION ALL
SELECT 'vitamin_b12_mcg', MIN(vitamin_b12_mcg), MAX(vitamin_b12_mcg) FROM food_nutrients WHERE vitamin_b12_mcg IS NOT NULL
UNION ALL
SELECT 'folate_mcg',      MIN(folate_mcg),      MAX(folate_mcg)      FROM food_nutrients WHERE folate_mcg      IS NOT NULL
UNION ALL
SELECT 'vitamin_c_mg',    MIN(vitamin_c_mg),    MAX(vitamin_c_mg)    FROM food_nutrients WHERE vitamin_c_mg    IS NOT NULL
UNION ALL
SELECT 'vitamin_e_mg',    MIN(vitamin_e_mg),    MAX(vitamin_e_mg)    FROM food_nutrients WHERE vitamin_e_mg    IS NOT NULL
UNION ALL
SELECT 'vitamin_b6_mg',   MIN(vitamin_b6_mg),   MAX(vitamin_b6_mg)   FROM food_nutrients WHERE vitamin_b6_mg   IS NOT NULL
UNION ALL
SELECT 'vitamin_d_mcg',   MIN(vitamin_d_mcg),   MAX(vitamin_d_mcg)   FROM food_nutrients WHERE vitamin_d_mcg   IS NOT NULL
UNION ALL
SELECT 'sugar_g',         MIN(sugar_g),         MAX(sugar_g)         FROM food_nutrients WHERE sugar_g         IS NOT NULL
UNION ALL
SELECT 'protein_g',       MIN(protein_g),       MAX(protein_g)       FROM food_nutrients WHERE protein_g       IS NOT NULL
UNION ALL
SELECT 'fiber_g',         MIN(fiber_g),         MAX(fiber_g)         FROM food_nutrients WHERE fiber_g         IS NOT NULL
UNION ALL
SELECT 'calories_kcal',   MIN(calories_kcal),   MAX(calories_kcal)   FROM food_nutrients WHERE calories_kcal   IS NOT NULL
ON DUPLICATE KEY UPDATE
  min_value  = VALUES(min_value),
  max_value  = VALUES(max_value),
  updated_at = CURRENT_TIMESTAMP;
