-- Manual fallback: compute normalization_cache for moodmeal_vn.
-- The ETL runner (python etl/run_etl.py --datasets vietnamese) calls this
-- automatically via compute_normalization_cache(vn_engine). Run this SQL
-- only if you need to recompute without re-running the ETL.

USE moodmeal_vn;

INSERT INTO normalization_cache (nutrient_key, min_value, max_value)
SELECT 'tryptophan_mg', MIN(tryptophan_mg), MAX(tryptophan_mg) FROM food_nutrients WHERE tryptophan_mg IS NOT NULL
UNION ALL
SELECT 'omega3_mg',     MIN(omega3_mg),     MAX(omega3_mg)     FROM food_nutrients WHERE omega3_mg IS NOT NULL
UNION ALL
SELECT 'complex_carbs_g', MIN(complex_carbs_g), MAX(complex_carbs_g) FROM food_nutrients WHERE complex_carbs_g IS NOT NULL
UNION ALL
SELECT 'magnesium_mg',  MIN(magnesium_mg),  MAX(magnesium_mg)  FROM food_nutrients WHERE magnesium_mg IS NOT NULL
UNION ALL
SELECT 'iron_mg',       MIN(iron_mg),       MAX(iron_mg)        FROM food_nutrients WHERE iron_mg IS NOT NULL
UNION ALL
SELECT 'vitamin_b12_mcg', MIN(vitamin_b12_mcg), MAX(vitamin_b12_mcg) FROM food_nutrients WHERE vitamin_b12_mcg IS NOT NULL
UNION ALL
SELECT 'folate_mcg',    MIN(folate_mcg),    MAX(folate_mcg)     FROM food_nutrients WHERE folate_mcg IS NOT NULL
UNION ALL
SELECT 'vitamin_c_mg',  MIN(vitamin_c_mg),  MAX(vitamin_c_mg)  FROM food_nutrients WHERE vitamin_c_mg IS NOT NULL
UNION ALL
SELECT 'vitamin_e_mg',  MIN(vitamin_e_mg),  MAX(vitamin_e_mg)  FROM food_nutrients WHERE vitamin_e_mg IS NOT NULL
UNION ALL
SELECT 'sugar_g',       MIN(sugar_g),       MAX(sugar_g)        FROM food_nutrients WHERE sugar_g IS NOT NULL
UNION ALL
SELECT 'protein_g',     MIN(protein_g),     MAX(protein_g)      FROM food_nutrients WHERE protein_g IS NOT NULL
UNION ALL
SELECT 'fiber_g',       MIN(fiber_g),       MAX(fiber_g)        FROM food_nutrients WHERE fiber_g IS NOT NULL
UNION ALL
SELECT 'calories_kcal', MIN(calories_kcal), MAX(calories_kcal)  FROM food_nutrients WHERE calories_kcal IS NOT NULL
ON DUPLICATE KEY UPDATE
  min_value  = VALUES(min_value),
  max_value  = VALUES(max_value),
  updated_at = CURRENT_TIMESTAMP;
