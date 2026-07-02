# backend/tests/test_etl.py
import pytest
from emoeating.data.etl import (
    ENRICH_SOURCES,
    enrich_food,
    missing_micros,
    run_etl,
)
from emoeating.data.store import FoodStore
from emoeating.data.schema import Food


class FakeUsdaClient:
    """In-memory stand-in for the USDA API; records calls, never touches network."""

    def __init__(self, table):
        self.table = table
        self.calls = []

    def lookup(self, name):
        self.calls.append(name)
        return self.table.get(name, {})


def _recipe(fid, name, **nutrients):
    return Food(id=fid, name=name, source="foodcom", calories=None, nutrients=nutrients)


def test_missing_micros_lists_absent_canonical_keys():
    food = _recipe("foodcom:1", "lentil soup", omega3_g=0.5)
    gaps = missing_micros(food)
    assert "omega3_g" not in gaps          # present -> not a gap
    assert "vit_c_mg" in gaps              # absent -> a gap


def test_enrich_fills_only_absent_micros():
    client = FakeUsdaClient({"lentil soup": {"vit_c_mg": 4.0, "omega3_g": 9.9}})
    food = _recipe("foodcom:1", "lentil soup", protein_g=10.0, omega3_g=0.5)
    enrich_food(food, client)
    assert food.amount("vit_c_mg") == pytest.approx(4.0)   # filled
    assert food.amount("omega3_g") == pytest.approx(0.5)   # NOT overwritten
    assert food.amount("protein_g") == pytest.approx(10.0)
    assert client.calls == ["lentil soup"]


def test_enrich_skips_lookup_when_no_micros_missing():
    full = {k: 1.0 for k in (
        "vit_c_mg", "vit_e_mg", "magnesium_mg", "vit_b6_mg", "folate_ug",
        "vit_b12_ug", "vit_d_ug", "omega3_g", "fiber_g",
    )}
    client = FakeUsdaClient({})
    food = _recipe("foodcom:2", "complete", **full)
    enrich_food(food, client)
    assert client.calls == []   # no gaps -> no network call


def test_run_etl_ingests_all_sources_and_enriches_recipes_only():
    client = FakeUsdaClient({"lentil soup": {"omega3_g": 2.5, "magnesium_mg": 30.0}})
    sources = {
        "usda": [Food(id="usda:1", name="Salmon", source="usda", calories=206.0,
                      nutrients={"omega3_g": 0.3})],
        "foodcom": [_recipe("foodcom:1", "lentil soup", protein_g=10.0)],
    }
    store = FoodStore.open()
    total = run_etl(sources, store, client=client)
    assert total == 2
    by_id = {f.id: f for f in store.all_foods()}
    # recipe got enriched
    assert by_id["foodcom:1"].amount("omega3_g") == pytest.approx(2.5)
    assert by_id["foodcom:1"].amount("magnesium_mg") == pytest.approx(30.0)
    # USDA food was not sent through enrichment
    assert client.calls == ["lentil soup"]
    assert by_id["usda:1"].amount("omega3_g") == pytest.approx(0.3)


def test_run_etl_without_client_skips_enrichment():
    sources = {"foodcom": [_recipe("foodcom:1", "lentil soup", protein_g=10.0)]}
    store = FoodStore.open()
    total = run_etl(sources, store, client=None)
    assert total == 1
    assert "omega3_g" not in store.all_foods()[0].nutrients


def test_enrich_sources_default():
    assert ENRICH_SOURCES == ("foodcom", "epicurious")
