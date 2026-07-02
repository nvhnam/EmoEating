# backend/emoeating/data/etl.py
"""Run-once offline ETL: ingest all four sources into a unified SQLite store, then
fill recipe items' missing micronutrients via an injectable USDA client.

The USDA enrichment client is abstracted behind a Protocol so tests pass a fake and
never touch the network; the concrete UsdaApiClient lazily imports `requests`.
"""
from __future__ import annotations

from collections.abc import Iterable
from typing import Protocol

from emoeating.data.schema import Food
from emoeating.data.sources.normalize import CANONICAL_MICRO_KEYS
from emoeating.data.store import FoodStore


class UsdaEnrichmentClient(Protocol):
    def lookup(self, name: str) -> dict[str, float]:
        """Return canonical micronutrient amounts for a food name (may be empty)."""
        ...


# Recipe sources lack a micronutrient panel and are the enrichment targets.
ENRICH_SOURCES: tuple[str, ...] = ("foodcom", "epicurious")


def missing_micros(
    food: Food, micros: Iterable[str] = CANONICAL_MICRO_KEYS
) -> list[str]:
    return [m for m in micros if m not in food.nutrients]


def enrich_food(
    food: Food,
    client: UsdaEnrichmentClient,
    micros: Iterable[str] = CANONICAL_MICRO_KEYS,
) -> Food:
    """Mutates `food.nutrients` in place (fills only missing micronutrients) and
    returns the same Food instance for chaining.  Callers must not assume the
    input is left unmodified."""
    gaps = missing_micros(food, micros)
    if not gaps:
        return food                      # nothing missing -> no network call
    found = client.lookup(food.name)
    for key in gaps:
        if key in found:
            food.nutrients[key] = found[key]   # fill only absent micros
    return food


def run_etl(
    sources: dict[str, Iterable[Food]],
    store: FoodStore,
    client: UsdaEnrichmentClient | None = None,
    enrich_sources: Iterable[str] = ENRICH_SOURCES,
) -> int:
    enrich_set = set(enrich_sources)
    total = 0
    for source_name, foods in sources.items():
        do_enrich = client is not None and source_name in enrich_set
        for food in foods:
            if do_enrich:
                enrich_food(food, client)
            total += store.upsert_foods([food])
    return total


class UsdaApiClient:
    """Concrete enrichment client backed by the USDA FoodData Central search API.

    Network-bound; never used in tests (those inject a fake). `requests` is imported
    lazily so importing this module costs nothing and needs no third-party dep.
    """

    def __init__(
        self,
        api_key: str,
        base_url: str = "https://api.nal.usda.gov/fdc/v1",
        timeout: float = 10.0,
    ) -> None:
        self._api_key = api_key
        self._base_url = base_url.rstrip("/")
        self._timeout = timeout

    def lookup(self, name: str) -> dict[str, float]:
        import requests  # lazy: keeps the dep and network out of import/tests

        from emoeating.data.sources.usda import parse_usda

        resp = requests.get(
            f"{self._base_url}/foods/search",
            params={"api_key": self._api_key, "query": name, "pageSize": 1},
            timeout=self._timeout,
        )
        resp.raise_for_status()
        foods = resp.json().get("foods", [])
        if not foods:
            return {}
        parsed = next(parse_usda(foods), None)
        if parsed is None:
            return {}
        return {
            key: value
            for key, value in parsed.nutrients.items()
            if key in CANONICAL_MICRO_KEYS
        }
