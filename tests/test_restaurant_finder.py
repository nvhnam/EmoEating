"""
Unit tests for app/services/restaurant_finder.py
Run: pytest tests/test_restaurant_finder.py -v
"""
from __future__ import annotations

import sys
import os
import dataclasses
from unittest.mock import MagicMock, patch

# Make app/ importable without running Streamlit
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "app"))

# Stub out streamlit before importing the module under test
import types

def _cache_data_noop(*args, **kwargs):
    def decorator(fn):
        return fn
    # Called either as @st.cache_data or @st.cache_data(ttl=...) — handle both.
    if args and callable(args[0]):
        return args[0]
    return decorator

st_stub = types.ModuleType("streamlit")
st_stub.cache_data = _cache_data_noop
st_stub.session_state = {}
st_stub.context = MagicMock()
sys.modules.setdefault("streamlit", st_stub)

from services.restaurant_finder import (
    RestaurantResult,
    build_text_query,
    compute_r_score,
    _parse_google_places_response,
)

WEIGHTS = {"alpha": 0.50, "beta": 0.30, "gamma": 0.20}


def test_build_text_query_basic():
    assert build_text_query("Grilled Salmon") == "Grilled Salmon restaurant"


def test_compute_r_score_perfect():
    r = RestaurantResult(
        place_id="1", name="A", address="", lat=0, lng=0,
        distance_m=0, rating=5.0, price_level=None, is_open=True,
        maps_url="", source="google_places",
    )
    score = compute_r_score(r, radius_max_m=2000, weights=WEIGHTS)
    # proximity=1, rating=1, availability=1 → should be 1.0
    assert abs(score - 1.0) < 1e-6


def test_compute_r_score_no_rating_default():
    r = RestaurantResult(
        place_id="2", name="B", address="", lat=0, lng=0,
        distance_m=0, rating=None, price_level=None, is_open=True,
        maps_url="", source="google_places",
    )
    score = compute_r_score(r, radius_max_m=2000, weights=WEIGHTS)
    # rating defaults to 3.5/5=0.70 → α*1 + β*0.70 + γ*1 = 0.50 + 0.21 + 0.20 = 0.91
    assert abs(score - 0.91) < 1e-6


def test_compute_r_score_closed_penalty():
    r_open = RestaurantResult(
        place_id="3", name="C", address="", lat=0, lng=0,
        distance_m=1000, rating=4.0, price_level=None, is_open=True,
        maps_url="", source="google_places",
    )
    r_closed = dataclasses.replace(r_open, is_open=False)
    score_open   = compute_r_score(r_open,   radius_max_m=2000, weights=WEIGHTS)
    score_closed = compute_r_score(r_closed, radius_max_m=2000, weights=WEIGHTS)
    assert score_open > score_closed


def test_parse_google_places_price_mapping():
    payload = {
        "places": [{
            "id": "abc",
            "displayName": {"text": "Test Resto"},
            "formattedAddress": "123 Street",
            "location": {"latitude": 10.0, "longitude": 106.0},
            "priceLevel": "PRICE_LEVEL_MODERATE",
            "googleMapsUri": "https://maps.google.com/test",
        }]
    }
    results = _parse_google_places_response(payload, 10.0, 106.0, max_results=4)
    assert len(results) == 1
    assert results[0].price_level == 2


def test_parse_google_places_missing_fields():
    payload = {
        "places": [{
            "id": "xyz",
            "displayName": {"text": "Minimal"},
            "location": {"latitude": 10.0, "longitude": 106.0},
        }]
    }
    results = _parse_google_places_response(payload, 10.0, 106.0, max_results=4)
    assert len(results) == 1
    r = results[0]
    assert r.rating is None
    assert r.price_level is None
    assert r.is_open is None
    assert r.formattedAddress if hasattr(r, "formattedAddress") else r.address == ""


def test_fetch_result_no_key(monkeypatch):
    """With empty api_key and OSM returning nothing, status should be no_key or no_results."""
    import services.restaurant_finder as rf
    monkeypatch.setattr(rf, "_call_osm_overpass", lambda *a, **kw: [])
    result = rf.fetch_restaurants_for_dish("Sushi", 1, 10.0, 106.0, api_key="")
    assert result["status"] in ("no_key", "no_results")
    assert result["restaurants"] == []
