"""DEV-ONLY launcher.

Runs the real FastAPI app (api.main.create_app) but injects a deterministic
MockEncoder and a small in-memory FoodStore, so the full funnel works locally
WITHOUT the multi-GB emotion2vec+ model or any Google API keys.

Run (from backend/, with the venv active):
    uvicorn dev_server:dev_app --factory --reload --port 8000

NOT for production. Production uses `create_app()` driven by env vars
(EMOEATING_MODEL_PATH, EMOEATING_STORE_PATH, EMOEATING_GOOGLE_* keys).
"""
from __future__ import annotations

from fastapi import FastAPI

from api.main import create_app
from emoeating.data.schema import Food
from emoeating.ser.encoder import MockEncoder


class _SeedStore:
    """In-memory stand-in for FoodStore (dev only) — avoids SQLite's
    same-thread restriction under FastAPI's threadpool. Implements the read
    surface the recommend route uses."""

    def __init__(self, foods: list[Food]) -> None:
        self._foods = list(foods)

    def candidates(self, limit: int | None = None) -> list[Food]:
        return self._foods if limit is None else self._foods[:limit]

    def all_foods(self) -> list[Food]:
        return list(self._foods)

    def count(self) -> int:
        return len(self._foods)

    def close(self) -> None:
        pass

# A deterministic affect so the demo lands in a clear zone (sad-leaning ->
# NEG_DEACTIVE -> omega-3 / B12 / folate / D priority).
_DEV_SCORES = {"sad": 0.7, "neutral": 0.2, "happy": 0.1}

# A handful of real-ish foods spanning the macro + priority-micro space so ENMS
# ranking is meaningful across zones. Values are rough per-serving amounts.
_SEED_FOODS = [
    Food(id="dev:salmon", name="Grilled Salmon", source="dev", calories=400,
         nutrients={"protein_g": 40, "fat_g": 22, "carb_g": 0, "omega3_g": 2.5,
                    "vit_d_ug": 14, "vit_b12_ug": 3.2, "folate_ug": 40},
         image_hint="grilled salmon fillet"),
    Food(id="dev:lentil_soup", name="Lentil Soup", source="dev", calories=320,
         nutrients={"protein_g": 18, "carb_g": 45, "fat_g": 6, "fiber_g": 16,
                    "folate_ug": 180, "magnesium_mg": 70, "vit_b6_mg": 0.5},
         image_hint="bowl of lentil soup"),
    Food(id="dev:spinach_salad", name="Spinach & Citrus Salad", source="dev", calories=210,
         nutrients={"protein_g": 6, "carb_g": 18, "fat_g": 12, "fiber_g": 6,
                    "folate_ug": 160, "vit_c_mg": 55, "magnesium_mg": 60, "vit_e_mg": 4},
         image_hint="spinach citrus salad"),
    Food(id="dev:oatmeal_berries", name="Oatmeal with Berries", source="dev", calories=300,
         nutrients={"protein_g": 8, "carb_g": 54, "fat_g": 5, "fiber_g": 8,
                    "magnesium_mg": 60, "vit_c_mg": 12},
         image_hint="oatmeal with berries"),
    Food(id="dev:greek_yogurt", name="Greek Yogurt & Walnuts", source="dev", calories=260,
         nutrients={"protein_g": 20, "carb_g": 14, "fat_g": 12, "omega3_g": 1.2,
                    "vit_b12_ug": 1.3, "magnesium_mg": 45},
         image_hint="greek yogurt with walnuts"),
    Food(id="dev:chicken_quinoa", name="Chicken & Quinoa Bowl", source="dev", calories=480,
         nutrients={"protein_g": 38, "carb_g": 50, "fat_g": 12, "fiber_g": 7,
                    "vit_b6_mg": 0.9, "magnesium_mg": 90, "folate_ug": 80},
         image_hint="chicken quinoa bowl"),
    Food(id="dev:bell_pepper_eggs", name="Bell Pepper Omelette", source="dev", calories=290,
         nutrients={"protein_g": 22, "carb_g": 8, "fat_g": 19, "vit_c_mg": 90,
                    "vit_d_ug": 2, "vit_b12_ug": 1.1, "folate_ug": 60},
         image_hint="bell pepper omelette"),
    Food(id="dev:almond_orange", name="Almonds & Orange", source="dev", calories=250,
         nutrients={"protein_g": 9, "carb_g": 24, "fat_g": 15, "fiber_g": 6,
                    "vit_e_mg": 10, "vit_c_mg": 70, "magnesium_mg": 80},
         image_hint="almonds and orange"),
    Food(id="dev:tofu_stirfry", name="Tofu & Broccoli Stir-fry", source="dev", calories=360,
         nutrients={"protein_g": 24, "carb_g": 30, "fat_g": 16, "fiber_g": 8,
                    "vit_c_mg": 80, "magnesium_mg": 110, "folate_ug": 100, "vit_e_mg": 3},
         image_hint="tofu broccoli stir fry"),
    Food(id="dev:banana_pb_toast", name="Banana Peanut-Butter Toast", source="dev", calories=340,
         nutrients={"protein_g": 12, "carb_g": 48, "fat_g": 12, "fiber_g": 6,
                    "vit_b6_mg": 0.6, "magnesium_mg": 70},
         image_hint="banana peanut butter toast"),
]


def dev_app() -> FastAPI:
    app = create_app()  # Null providers, encoder None, store None (no env configured)
    app.state.encoder = MockEncoder(_DEV_SCORES)
    app.state.store = _SeedStore(_SEED_FOODS)
    return app
