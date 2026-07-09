import sys
sys.path.insert(0, r'D:\UIST_2026\EmoEating\app')
from db.connection import get_connection
from sqlalchemy import text

conn = get_connection()

# Full 38 foods passing current filter
q_full = text("""
  SELECT name, omega3_mg, vitamin_d_mcg, vitamin_b12_mcg, folate_mcg,
         calories_kcal, protein_g, carbohydrate_g, fat_g
  FROM meals_with_nutrients
  WHERE meal_type='complete_meal' AND data_completeness>=5
    AND folate_mcg IS NOT NULL AND vitamin_b12_mcg IS NOT NULL
    AND vitamin_d_mcg IS NOT NULL AND omega3_mg IS NOT NULL
  ORDER BY omega3_mg DESC
""")
print("=== ALL 38 foods passing Q3_NEG_DEACT ALL-4 filter ===")
for r in conn.execute(q_full):
    print(f"  {str(r.name)[:50]:<50} kcal={r.calories_kcal} pro={r.protein_g} carb={r.carbohydrate_g} fat={r.fat_g} | omega3={r.omega3_mg}")

# Check all foods with omega3 non-null
q_omega3 = text("""
  SELECT name, meal_type, omega3_mg, source_dataset
  FROM meals_with_nutrients
  WHERE omega3_mg IS NOT NULL
  ORDER BY omega3_mg DESC
""")
print("\n=== ALL foods with omega3_mg non-null (43 total) ===")
for r in conn.execute(q_omega3):
    print(f"  [{r.meal_type}] [{r.source_dataset}] {str(r.name)[:50]:<50} omega3={r.omega3_mg}")

conn.close()
