# backend/tests/test_store.py
import pytest
from emoeating.data.store import FoodStore
from emoeating.data.schema import Food


def _food(fid, **nutrients):
    return Food(id=fid, name=fid, source="t", calories=100.0, nutrients=nutrients)


def test_roundtrip_preserves_nutrients_and_fields():
    store = FoodStore.open()  # in-memory
    original = Food(
        id="usda:1", name="Salmon", source="usda", calories=206.0,
        nutrients={"protein_g": 22.1, "omega3_g": 0.3}, image_hint="Salmon",
    )
    store.upsert_foods([original])
    got = store.all_foods()
    assert len(got) == 1
    assert got[0] == original  # dataclass equality: every field round-trips


def test_upsert_is_idempotent_on_id():
    store = FoodStore.open()
    store.upsert_foods([_food("a", carb_g=10.0)])
    store.upsert_foods([_food("a", carb_g=99.0)])  # same id -> replace
    foods = store.all_foods()
    assert len(foods) == 1
    assert foods[0].amount("carb_g") == pytest.approx(99.0)


def test_candidates_orders_by_id_and_honors_limit():
    store = FoodStore.open()
    store.upsert_foods([_food("c"), _food("a"), _food("b")])
    assert [f.id for f in store.candidates()] == ["a", "b", "c"]
    assert [f.id for f in store.candidates(limit=2)] == ["a", "b"]


def test_count():
    store = FoodStore.open()
    assert store.count() == 0
    store.upsert_foods([_food("a"), _food("b")])
    assert store.count() == 2
