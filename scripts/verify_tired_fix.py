"""
Verify the two-phase priority recommender across all zones.
"""
import sys
sys.path.insert(0, r'D:\UIST_2026\EmoEating\app')

from engine.recommender import get_recommendations, _name_key
from engine.zone_classifier import classify_zone
from engine.affect_mapper import emotion_to_va
from db.queries import get_meals
from db.connection import get_connection
from config import ZONE_MICRONUTRIENT_PRIORITIES, MIN_DATA_COMPLETENESS

conn = get_connection()

# ── Pool sizes per zone ───────────────────────────────────────────────────────
print("=== CANDIDATE POOL SIZES (dinner, completeness>=5) ===")
foods_dinner = get_meals("dinner", [], min_completeness=MIN_DATA_COMPLETENESS, db_conn=conn)
for zone, micros in ZONE_MICRONUTRIENT_PRIORITIES.items():
    pri = [f for f in foods_dinner if all(f.get(c) is not None for c in micros)]
    p_ids = {f.get("id") for f in pri}
    fb  = [f for f in foods_dinner if f.get("id") not in p_ids
           and any(f.get(c) is not None for c in micros)]
    print(f"  {zone:<20}  nutrients={micros}")
    print(f"    PRIMARY (ALL): {len(pri)}   FALLBACK (ANY-minus-primary): {len(fb)}")

# ── Per-emotion check (zone-aware phase labels) ───────────────────────────────
def check(label, emotion, meal_type):
    V, A = emotion_to_va(emotion)
    zone = classify_zone(V, A)
    micros = ZONE_MICRONUTRIENT_PRIORITIES.get(zone, [])
    recs = get_recommendations(emotion, meal_type, None, [], top_k=3, db_conn=conn)
    keys = [_name_key(r.get("name") or "") for r in recs]
    dupes = len(keys) != len(set(keys))
    print(f"\n{label}  [zone={zone}]")
    for r in recs:
        phase = "PRIMARY " if all(r.get(c) is not None for c in micros) else "FALLBACK"
        print(f"  #{r['rank']} [{phase}]  ENMS={r['enms']:.4f}  "
              f"macro={r['macro_score']:.3f}  micro={r['micro_score']:.3f}  "
              f"name={r.get('name','?')}")
    print(f"  All unique names: {not dupes}")

print("\n=== RECOMMENDATION RESULTS ===")
check("TIRED   / dinner", "tired",    "dinner")
check("SAD     / lunch",  "sad",      "lunch")
check("BORED   / dinner", "bored",    "dinner")
check("STRESSED/ dinner", "stressed", "dinner")
check("HAPPY   / dinner", "happy",    "dinner")
check("CALM    / dinner", "calm",     "dinner")

conn.close()
print("\nDone.")
