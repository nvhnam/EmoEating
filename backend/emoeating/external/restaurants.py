# backend/emoeating/external/restaurants.py
"""Nearby-restaurant providers behind a single interface. Keys stay server-side."""
from __future__ import annotations

import math
from dataclasses import dataclass
from typing import Protocol

import httpx

_TEXT_SEARCH_URL = "https://maps.googleapis.com/maps/api/place/textsearch/json"
_EARTH_M = 6_371_000.0


@dataclass
class Place:
    name: str
    lat: float
    lng: float
    distance_m: float
    address: str


def _haversine_m(lat1: float, lng1: float, lat2: float, lng2: float) -> float:
    p1, p2 = math.radians(lat1), math.radians(lat2)
    dphi = math.radians(lat2 - lat1)
    dlmb = math.radians(lng2 - lng1)
    a = math.sin(dphi / 2) ** 2 + math.cos(p1) * math.cos(p2) * math.sin(dlmb / 2) ** 2
    return 2 * _EARTH_M * math.asin(math.sqrt(a))


class RestaurantProvider(Protocol):
    enabled: bool

    def nearby(
        self, food: str, lat: float, lng: float, radius_m: int = 11000
    ) -> list[Place]: ...


class NullRestaurantProvider:
    """Used when no Places key is configured (graceful degradation)."""
    enabled = False

    def nearby(self, food: str, lat: float, lng: float, radius_m: int = 11000) -> list[Place]:
        return []


class GooglePlacesProvider:
    enabled = True

    def __init__(self, api_key: str, client: httpx.Client | None = None):
        self._api_key = api_key
        self._client = client or httpx.Client(timeout=10.0)

    def nearby(self, food: str, lat: float, lng: float, radius_m: int = 11000) -> list[Place]:
        try:
            resp = self._client.get(_TEXT_SEARCH_URL, params={
                "key": self._api_key,
                "query": food,
                "location": f"{lat},{lng}",
                "radius": radius_m,
            })
            resp.raise_for_status()
            data = resp.json()
            if not isinstance(data, dict):
                return []
            results = data.get("results", [])
            if not isinstance(results, list):
                return []
        except (httpx.HTTPError, ValueError):
            return []

        places: list[Place] = []
        for r in results:
            loc = r.get("geometry", {}).get("location", {})
            if "lat" not in loc or "lng" not in loc:
                continue
            dist = _haversine_m(lat, lng, loc["lat"], loc["lng"])
            if dist > radius_m:
                continue
            places.append(Place(
                name=r.get("name", ""),
                lat=loc["lat"],
                lng=loc["lng"],
                distance_m=dist,
                address=r.get("formatted_address", ""),
            ))
        places.sort(key=lambda p: p.distance_m)
        return places
