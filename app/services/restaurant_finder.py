"""
Restaurant discovery service for EmoEating.

Ranking formula (paper §4.3):
  R_score(r) = α·proximity(r) + β·rating(r) + γ·availability(r)
    proximity(r)    = 1 − (dist_m(r) / radius_max)   ∈ [0, 1]
    rating(r)       = (restaurant.rating or 3.5) / 5.0
    availability(r) = 1.0 if open_now else 0.5
    α=0.50, β=0.30, γ=0.20  (RESTAURANT_SCORE_WEIGHTS in config.py)
"""

from __future__ import annotations

import dataclasses
import sys
import time
from dataclasses import dataclass
from typing import Optional

import requests
import streamlit as st
from rapidfuzz import fuzz

from services.location import haversine_distance_m
from config import (
    GOOGLE_PLACES_TEXT_SEARCH_URL,
    FOURSQUARE_SEARCH_URL,
    HERE_SEARCH_URL,
    OSM_OVERPASS_URL,
    RESTAURANT_CACHE_TTL,
    RESTAURANT_SCORE_WEIGHTS,
)


@dataclass
class RestaurantResult:
    place_id:    str
    name:        str
    address:     str
    lat:         float
    lng:         float
    distance_m:  float
    rating:      Optional[float]
    price_level: Optional[int]
    is_open:     Optional[bool]
    maps_url:    str
    source:      str            # "google_places" | "osm"
    r_score:     float = 0.0


# ── Price level string → int mapping for Google Places (New) API ─────────────
_PRICE_MAP = {
    "PRICE_LEVEL_FREE":         0,
    "PRICE_LEVEL_INEXPENSIVE":  1,
    "PRICE_LEVEL_MODERATE":     2,
    "PRICE_LEVEL_EXPENSIVE":    3,
    "PRICE_LEVEL_VERY_EXPENSIVE": 4,
}


def build_text_query(dish_name: str) -> str:
    """Return the Places text search query for a dish."""
    return f"{dish_name} restaurant"


def compute_r_score(
    restaurant: RestaurantResult,
    radius_max_m: float,
    weights: dict,
) -> float:
    """Compute composite ranking score R ∈ [0, 1]."""
    alpha = weights.get("alpha", 0.50)
    beta  = weights.get("beta",  0.30)
    gamma = weights.get("gamma", 0.20)

    proximity    = max(0.0, min(1.0, 1.0 - (restaurant.distance_m / radius_max_m)))
    rating_norm  = (restaurant.rating if restaurant.rating is not None else 3.5) / 5.0
    availability = 1.0 if restaurant.is_open else 0.5

    return alpha * proximity + beta * rating_norm + gamma * availability


def _parse_google_places_response(
    response_json: dict,
    user_lat: float,
    user_lng: float,
    max_results: int,
) -> list[RestaurantResult]:
    results = []
    for place in response_json.get("places", [])[:max_results]:
        loc       = place.get("location", {})
        place_lat = float(loc.get("latitude", 0.0))
        place_lng = float(loc.get("longitude", 0.0))

        raw_price = place.get("priceLevel")
        price_int = _PRICE_MAP.get(raw_price) if raw_price else None

        opening = place.get("regularOpeningHours", {})
        is_open = opening.get("openNow") if opening else None

        results.append(RestaurantResult(
            place_id    = place.get("id", ""),
            name        = place.get("displayName", {}).get("text", ""),
            address     = place.get("formattedAddress", ""),
            lat         = place_lat,
            lng         = place_lng,
            distance_m  = haversine_distance_m(user_lat, user_lng, place_lat, place_lng),
            rating      = float(place["rating"]) if place.get("rating") is not None else None,
            price_level = price_int,
            is_open     = is_open,
            maps_url    = place.get("googleMapsUri", ""),
            source      = "google_places",
        ))
    return results


def _call_google_places_api(
    query: str,
    user_lat: float,
    user_lng: float,
    radius_m: int,
    api_key: str,
    max_results: int = 4,
    timeout_s: float = 5.0,
    language_code: str = "en",
) -> list[RestaurantResult]:
    try:
        headers = {
            "X-Goog-Api-Key":   api_key,
            "X-Goog-FieldMask": (
                "places.id,places.displayName,places.formattedAddress,"
                "places.location,places.rating,places.priceLevel,"
                "places.regularOpeningHours,places.googleMapsUri"
            ),
        }
        body = {
            "textQuery":       query,
            "maxResultCount":  max_results,
            "languageCode":    language_code,
            "locationBias": {
                "circle": {
                    "center": {"latitude": user_lat, "longitude": user_lng},
                    "radius": float(radius_m),
                }
            },
        }
        resp = requests.post(
            GOOGLE_PLACES_TEXT_SEARCH_URL,
            headers=headers,
            json=body,
            timeout=timeout_s,
        )
        if resp.status_code != 200:
            return []
        return _parse_google_places_response(resp.json(), user_lat, user_lng, max_results)
    except Exception as exc:
        print(f"[restaurant_finder] Google Places error: {exc}", file=sys.stderr)
        return []


def _build_vn_query(vn_name: str) -> str:
    """Build a Vietnamese-language restaurant search query.

    Uses the Vietnamese food name + 'nhà hàng' (restaurant in Vietnamese)
    for higher precision on Google Maps listings in Vietnam.
    """
    return f"{vn_name} nhà hàng"


def _call_foursquare_api(
    query: str,
    user_lat: float,
    user_lng: float,
    radius_m: int,
    api_key: str,
    max_results: int = 4,
    timeout_s: float = 6.0,
) -> list[RestaurantResult]:
    """
    Foursquare Places API — migrated endpoint (places-api.foursquare.com).
    Migration guide: https://docs.foursquare.com/fsq-developers-places/reference/migration-guide
    Old host (410 Gone): api.foursquare.com/v3/places/search
    New host: places-api.foursquare.com/places/search

    Rating returned by FSQ is 0–10; halved to fit the 0–5 scale used by
    compute_r_score(). price_level is not available on the free tier.
    maps_url is constructed from lat/lng since FSQ does not return a Maps URI.
    """
    try:
        headers = {
            "Authorization": f"Bearer {api_key}",
            "Accept":        "application/json",
            "X-Places-Api-Version": "2025-06-17",
            "X-Users-Api-Version": "2025-06-17"
        }
        params = {
            "query":  query,
            "ll":     f"{user_lat},{user_lng}",
            "radius": radius_m,
            "limit":  min(max_results, 50),
        }
        resp = requests.get(
            FOURSQUARE_SEARCH_URL,
            headers=headers,
            params=params,
            timeout=timeout_s,
        )
        if resp.status_code != 200:
            print(
                f"[restaurant_finder] Foursquare HTTP {resp.status_code}: "
                f"{resp.text[:200]}",
                file=sys.stderr,
            )
            return []

        results = []
        for venue in resp.json().get("results", []):
            # New API: lat/lng are top-level fields (not nested under geocodes)
            v_lat  = float(venue.get("latitude", 0))
            v_lng  = float(venue.get("longitude", 0))
            dist_m = float(venue.get("distance") or haversine_distance_m(user_lat, user_lng, v_lat, v_lng))
            loc    = venue.get("location") or {}
            address = loc.get("formatted_address") or loc.get("address") or ""
            fsq_id  = venue.get("fsq_place_id", "")
            results.append(RestaurantResult(
                place_id    = f"fsq_{fsq_id}",
                name        = venue.get("name", ""),
                address     = address,
                lat         = v_lat,
                lng         = v_lng,
                distance_m  = dist_m,
                rating      = None,   # not returned by new endpoint
                price_level = None,
                is_open     = None,   # not returned by new endpoint
                maps_url    = f"https://www.google.com/maps/search/?api=1&query={v_lat},{v_lng}",
                source      = "foursquare",
            ))
        return results
    except Exception as exc:
        print(f"[restaurant_finder] Foursquare error: {exc}", file=sys.stderr)
        return []


def _call_here_api(
    query: str,
    user_lat: float,
    user_lng: float,
    radius_m: int,
    api_key: str,
    max_results: int = 4,
    timeout_s: float = 6.0,
) -> list[RestaurantResult]:
    """
    HERE Geocoding & Search API (free tier, 1 000 req/day, no credit card).
    Docs: https://developer.here.com/documentation/geocoding-search-api/dev_guide/topics/endpoint-discover-brief.html

    Auth is via ?apiKey= query param (no header required).
    Rating is not available on the free tier; maps_url is constructed from position.
    """
    try:
        params = {
            "q":      query,
            "in":     f"circle:{user_lat},{user_lng};r={radius_m}",
            "limit":  min(max_results, 100),
            "apiKey": api_key,
        }
        resp = requests.get(HERE_SEARCH_URL, params=params, timeout=timeout_s)
        if resp.status_code != 200:
            print(
                f"[restaurant_finder] HERE HTTP {resp.status_code}: "
                f"{resp.text[:200]}",
                file=sys.stderr,
            )
            return []

        results = []
        for item in resp.json().get("items", []):
            pos    = item.get("position", {})
            i_lat  = float(pos.get("lat", 0))
            i_lng  = float(pos.get("lng", 0))
            dist_m = float(item.get("distance") or haversine_distance_m(user_lat, user_lng, i_lat, i_lng))
            hours  = item.get("openingHours") or []
            is_open = hours[0].get("isOpen") if hours else None
            addr   = item.get("address", {}).get("label", "")
            item_id = item.get("id", "")
            results.append(RestaurantResult(
                place_id    = f"here_{item_id}",
                name        = item.get("title", ""),
                address     = addr,
                lat         = i_lat,
                lng         = i_lng,
                distance_m  = dist_m,
                rating      = None,   # not available on free tier
                price_level = None,
                is_open     = is_open,
                maps_url    = f"https://www.google.com/maps/search/?api=1&query={i_lat},{i_lng}",
                source      = "here",
            ))
        return results
    except Exception as exc:
        print(f"[restaurant_finder] HERE error: {exc}", file=sys.stderr)
        return []


def _call_osm_overpass(
    dish_name: str,
    user_lat: float,
    user_lng: float,
    radius_m: int,
    max_results: int = 4,
    timeout_s: float = 8.0,
) -> list[RestaurantResult]:
    """
    Fetch restaurant nodes and ways from OSM Overpass (HTTPS).
    Ways are large venues mapped as polygons; their centre is in element["center"].
    Uses rapidfuzz partial_ratio for dish-name fuzzy matching.
    """
    try:
        max_results_fetch = max_results * 5
        query = (
            f"[out:json][timeout:8];\n"
            f"(\n"
            f'  node["amenity"="restaurant"](around:{radius_m},{user_lat},{user_lng});\n'
            f'  way["amenity"="restaurant"](around:{radius_m},{user_lat},{user_lng});\n'
            f");\n"
            f"out center {max_results_fetch};"
        )
        resp = requests.post(
            OSM_OVERPASS_URL,
            data={"data": query},
            timeout=timeout_s,
        )
        if resp.status_code != 200:
            return []

        elements = resp.json().get("elements", [])

        fuzzy_hits = []
        remaining  = []
        for el in elements:
            # Coordinate extraction by element type
            if el.get("type") == "node":
                el_lat, el_lng = el.get("lat", 0.0), el.get("lon", 0.0)
            elif el.get("type") == "way":
                center = el.get("center", {})
                el_lat, el_lng = center.get("lat", 0.0), center.get("lon", 0.0)
            else:
                continue

            el_name  = el.get("tags", {}).get("name", "")
            score    = fuzz.partial_ratio(dish_name.lower(), el_name.lower())
            dist_m   = haversine_distance_m(user_lat, user_lng, el_lat, el_lng)

            entry = (score, dist_m, el, el_lat, el_lng)
            if score >= 30:
                fuzzy_hits.append(entry)
            else:
                remaining.append(entry)

        fuzzy_hits.sort(key=lambda x: -x[0])
        remaining.sort(key=lambda x: x[1])

        candidates = fuzzy_hits[:max_results]
        if len(candidates) < max_results:
            candidates += remaining[: max_results - len(candidates)]

        results = []
        for _, dist_m, el, el_lat, el_lng in candidates:
            tags     = el.get("tags", {})
            node_id  = el.get("id", 0)
            results.append(RestaurantResult(
                place_id    = f"osm_{node_id}",
                name        = tags.get("name", "Unknown Restaurant"),
                address     = tags.get("addr:street", "") or "",
                lat         = el_lat,
                lng         = el_lng,
                distance_m  = dist_m,
                rating      = None,
                price_level = None,
                is_open     = None,
                maps_url    = f"https://www.google.com/maps/search/?api=1&query={el_lat},{el_lng}",
                source      = "osm",
            ))
        return results
    except Exception as exc:
        print(f"[restaurant_finder] OSM Overpass error: {exc}", file=sys.stderr)
        return []


def fetch_restaurants_for_dish(
    dish_name: str,
    food_id,
    user_lat: float,
    user_lng: float,
    radius_m: Optional[int] = None,
    max_results: Optional[int] = None,
    api_key: Optional[str] = None,
    language_code: str = "en",
) -> dict:
    """
    Fetch and rank nearby restaurants for a single dish.

    Provider fallback chain (first non-empty result wins):
      1. Google Places API (New) — richest data, requires paid key
      2. Foursquare Places API   — free tier, migrated to places-api.foursquare.com
      3. HERE Geocoding & Search — free 1 000 req/day, no credit card
      4. OSM Overpass            — always free, geographic fallback

    When language_code='vi' (Vietnamese dataset mode), builds the search
    query using 'nhà hàng' suffix and requests Vietnamese-context results.

    Returns a RestaurantFetchResult dict.
    """
    from config import (
        RESTAURANT_SEARCH_RADIUS_M,
        RESTAURANT_MAX_RESULTS,
        GOOGLE_PLACES_API_KEY,
        FOURSQUARE_API_KEY,
        HERE_API_KEY,
    )
    if radius_m is None:
        radius_m = RESTAURANT_SEARCH_RADIUS_M
    if max_results is None:
        max_results = RESTAURANT_MAX_RESULTS
    if api_key is None:
        api_key = GOOGLE_PLACES_API_KEY

    t0 = time.time()
    query = _build_vn_query(dish_name) if language_code == "vi" else build_text_query(dish_name)

    results: list[RestaurantResult] = []
    source = "none"

    # ── Provider 1: Google Places API (New) ──────────────────────────────
    if api_key:
        results = _call_google_places_api(
            query, user_lat, user_lng, radius_m, api_key, max_results,
            language_code=language_code,
        )
        if results:
            source = "google_places"

    # ── Provider 2: HERE Geocoding & Search API ───────────────────────────
    if not results and HERE_API_KEY:
        results = _call_here_api(
            query, user_lat, user_lng, radius_m, HERE_API_KEY, max_results,
        )
        if results:
            source = "here"

    # ── Provider 3: Foursquare Places API (migrated endpoint) ────────────
    if not results and FOURSQUARE_API_KEY:
        results = _call_foursquare_api(
            query, user_lat, user_lng, radius_m, FOURSQUARE_API_KEY, max_results,
        )
        if results:
            source = "foursquare"

    # ── Provider 4: OSM Overpass (always free, geographic fallback) ───────
    if not results:
        results = _call_osm_overpass(dish_name, user_lat, user_lng, radius_m, max_results)
        if results:
            source = "osm"

    # Apply composite ranking across whichever provider succeeded
    for r in results:
        r.r_score = compute_r_score(r, float(radius_m), RESTAURANT_SCORE_WEIGHTS)
    results.sort(key=lambda r: -r.r_score)
    results = results[:max_results]

    fetch_time_ms = (time.time() - t0) * 1000

    has_any_key = bool(api_key or FOURSQUARE_API_KEY or HERE_API_KEY)
    if not has_any_key and not results:
        status = "no_key"
    elif results:
        status = "ok"
    else:
        status = "no_results"

    return {
        "status":        status,
        "restaurants":   [dataclasses.asdict(r) for r in results],
        "query":         query,
        "source":        source,
        "error_msg":     None,
        "fetch_time_ms": fetch_time_ms,
    }


@st.cache_data(ttl=RESTAURANT_CACHE_TTL, show_spinner=False)
def fetch_restaurants_cached(
    dish_name: str,
    food_id,
    lat_rounded: float,
    lng_rounded: float,
    radius_m: int,
    max_results: int,
    api_key: str,
    language_code: str = "en",
) -> dict:
    """Cache key uses round(lat,3), round(lng,3) ≈ 111 m precision."""
    return fetch_restaurants_for_dish(
        dish_name, food_id, lat_rounded, lng_rounded,
        radius_m, max_results, api_key, language_code,
    )
