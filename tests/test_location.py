"""
Unit tests for app/services/location.py
Run: pytest tests/test_location.py -v
"""
from __future__ import annotations

import sys
import os
import math
from unittest.mock import MagicMock, patch

# Make app/ importable without running Streamlit
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "app"))

# Stub streamlit before importing the module under test
import types

def _cache_data_noop(*args, **kwargs):
    def decorator(fn):
        return fn
    if args and callable(args[0]):
        return args[0]
    return decorator

st_stub = types.ModuleType("streamlit")
st_stub.cache_data = _cache_data_noop
st_stub.session_state = {}
st_stub.context = MagicMock()
sys.modules.setdefault("streamlit", st_stub)

import requests
from services.location import haversine_distance_m, get_ip_location, geocode_address


def test_haversine_same_point():
    assert haversine_distance_m(10.0, 106.0, 10.0, 106.0) == 0.0


def test_haversine_known_distance():
    # HCMC to Hanoi — approximately 1,144 km
    dist = haversine_distance_m(10.762622, 106.660172, 21.027764, 105.834160)
    assert abs(dist - 1_144_000) < 1_144_000 * 0.05  # ±5%


def test_get_ip_location_timeout(monkeypatch):
    import services.location as loc_mod
    monkeypatch.setattr(
        loc_mod.st.context, "headers",
        MagicMock(get=lambda k, default="": ""),
    )
    monkeypatch.setattr(
        loc_mod.requests, "get",
        MagicMock(side_effect=requests.exceptions.Timeout),
    )
    assert loc_mod.get_ip_location() is None


def test_geocode_empty_result(monkeypatch):
    """Both Places API (New) and Nominatim return empty results → None."""
    import services.location as loc_mod

    mock_places_resp = MagicMock()
    mock_places_resp.status_code = 200
    mock_places_resp.json.return_value = {"places": []}

    mock_nominatim_resp = MagicMock()
    mock_nominatim_resp.status_code = 200
    mock_nominatim_resp.json.return_value = []

    monkeypatch.setattr(loc_mod.requests, "post", MagicMock(return_value=mock_places_resp))
    monkeypatch.setattr(loc_mod.requests, "get", MagicMock(return_value=mock_nominatim_resp))

    assert loc_mod.geocode_address("Nowhere", api_key="fake") is None


def test_get_ip_location_uses_forwarded_for(monkeypatch):
    import services.location as loc_mod

    headers_mock = MagicMock()
    headers_mock.get = lambda k, default="": (
        "203.0.113.5, 10.0.0.1" if k == "X-Forwarded-For" else default
    )
    monkeypatch.setattr(loc_mod.st.context, "headers", headers_mock)

    mock_resp = MagicMock()
    mock_resp.status_code = 200
    mock_resp.json.return_value = {
        "latitude": 10.8, "longitude": 106.7,
        "city": "Ho Chi Minh City", "country_code": "VN",
    }
    captured_urls = []

    def fake_get(url, timeout):
        captured_urls.append(url)
        return mock_resp

    monkeypatch.setattr(loc_mod.requests, "get", fake_get)
    result = loc_mod.get_ip_location()

    assert captured_urls == ["https://ipapi.co/203.0.113.5/json/"]
    assert result is not None
    assert result["source"] == "ip_auto"


def test_get_ip_location_falls_back_without_header(monkeypatch):
    import services.location as loc_mod

    headers_mock = MagicMock()
    headers_mock.get = lambda k, default="": default
    monkeypatch.setattr(loc_mod.st.context, "headers", headers_mock)

    mock_resp = MagicMock()
    mock_resp.status_code = 200
    mock_resp.json.return_value = {
        "latitude": 10.8, "longitude": 106.7,
        "city": "Ho Chi Minh City", "country_code": "VN",
    }
    captured_urls = []

    def fake_get(url, timeout):
        captured_urls.append(url)
        return mock_resp

    monkeypatch.setattr(loc_mod.requests, "get", fake_get)
    result = loc_mod.get_ip_location()

    assert captured_urls == ["https://ipapi.co/json/"]
    assert result is not None


def test_get_ip_location_ipapi_error_field(monkeypatch):
    import services.location as loc_mod

    headers_mock = MagicMock()
    headers_mock.get = lambda k, default="": default
    monkeypatch.setattr(loc_mod.st.context, "headers", headers_mock)

    mock_resp = MagicMock()
    mock_resp.status_code = 200
    mock_resp.json.return_value = {"error": True, "reason": "Reserved IP Address"}

    monkeypatch.setattr(loc_mod.requests, "get", lambda url, timeout: mock_resp)
    assert loc_mod.get_ip_location() is None
