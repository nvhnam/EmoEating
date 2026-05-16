from __future__ import annotations

import math
import sys
from typing import Optional

import requests
import streamlit as st

from config import (
    GOOGLE_PLACES_TEXT_SEARCH_URL,
    GEOJS_ENDPOINT,
    IPWHOIS_ENDPOINT,
    NOMINATIM_REVERSE_URL,
)

_NOMINATIM_UA = {"User-Agent": "MoodMeal/1.0 (research prototype)"}


def _geocode_via_places_api(
    address: str, api_key: str, timeout_s: float
) -> Optional[dict]:
    """Geocode via Google Places API (New) Text Search — requires only 'Places API (New)'."""
    try:
        headers = {
            "X-Goog-Api-Key": api_key,
            "X-Goog-FieldMask": "places.location,places.formattedAddress,places.displayName",
            "Content-Type": "application/json",
        }
        body = {
            "textQuery": address,
            "maxResultCount": 1,
            "languageCode": "en",
        }
        resp = requests.post(
            GOOGLE_PLACES_TEXT_SEARCH_URL,
            json=body,
            headers=headers,
            timeout=timeout_s,
        )
        if resp.status_code != 200:
            return None
        places = resp.json().get("places", [])
        if not places:
            return None
        place = places[0]
        loc = place.get("location", {})
        lat = loc.get("latitude")
        lng = loc.get("longitude")
        label = place.get("formattedAddress") or place.get("displayName", {}).get("text", address)
        if lat is None or lng is None:
            return None
        return {
            "lat":    float(lat),
            "lng":    float(lng),
            "label":  label,
            "source": "manual_geocoded",
        }
    except Exception:
        return None


def _geocode_nominatim(address: str, timeout_s: float) -> Optional[dict]:
    """Fallback geocoder using OpenStreetMap Nominatim — free, no API key required."""
    try:
        resp = requests.get(
            "https://nominatim.openstreetmap.org/search",
            params={"q": address, "format": "json", "limit": 1},
            headers=_NOMINATIM_UA,
            timeout=timeout_s,
        )
        if resp.status_code != 200:
            return None
        results = resp.json()
        if not results:
            return None
        r = results[0]
        return {
            "lat":    float(r["lat"]),
            "lng":    float(r["lon"]),
            "label":  r.get("display_name", address),
            "source": "manual_geocoded",
        }
    except Exception:
        return None


def reverse_geocode(lat: float, lng: float, timeout_s: float = 3.0) -> Optional[str]:
    """Convert lat/lng to a human-readable city label using Nominatim reverse geocoding."""
    try:
        resp = requests.get(
            NOMINATIM_REVERSE_URL,
            params={"lat": lat, "lon": lng, "format": "json", "zoom": 10},
            headers=_NOMINATIM_UA,
            timeout=timeout_s,
        )
        if resp.status_code != 200:
            return None
        data = resp.json()
        addr = data.get("address", {})
        parts = [
            addr.get(k)
            for k in ("city", "town", "village", "state", "country")
            if addr.get(k)
        ]
        return ", ".join(parts[:2]) if parts else data.get("display_name")
    except Exception:
        return None


def get_ip_location(timeout_s: float = 3.0) -> Optional[dict]:
    """
    Geolocate the end-user's IP using a 4-provider fallback chain.
    On Streamlit Cloud reads real client IP from X-Forwarded-For header.
    Returns None on total failure so callers can prompt for manual entry.
    """
    client_ip = ""
    try:
        forwarded_for = st.context.headers.get("X-Forwarded-For", "").strip()
        client_ip = forwarded_for.split(",")[0].strip() if forwarded_for else ""
    except Exception:
        pass

    # Attempt 1: ipapi.co (1,000 req/day free tier)
    try:
        url = f"https://ipapi.co/{client_ip}/json/" if client_ip else "https://ipapi.co/json/"
        resp = requests.get(url, timeout=timeout_s)
        if resp.status_code == 200:
            data = resp.json()
            if not data.get("error"):
                return {
                    "lat":    float(data["latitude"]),
                    "lng":    float(data["longitude"]),
                    "label":  f"{data['city']}, {data['country_code']}",
                    "source": "ip_auto",
                }
    except Exception:
        pass

    # Attempt 2: ipinfo.io (50k req/month free, HTTPS)
    try:
        url = f"https://ipinfo.io/{client_ip}/json" if client_ip else "https://ipinfo.io/json"
        resp = requests.get(url, timeout=timeout_s)
        if resp.status_code == 200:
            data = resp.json()
            loc_str = data.get("loc", "")   # "lat,lng"
            if loc_str and "," in loc_str:
                lat_s, lng_s = loc_str.split(",", 1)
                return {
                    "lat":    float(lat_s),
                    "lng":    float(lng_s),
                    "label":  f"{data.get('city', '')}, {data.get('country', '')}".strip(", "),
                    "source": "ip_auto",
                }
    except Exception:
        pass

    # Attempt 3: geojs.io (free, unlimited, HTTPS)
    try:
        url = f"{GEOJS_ENDPOINT}{client_ip}.json" if client_ip else "https://get.geojs.io/v1/ip/geo.json"
        resp = requests.get(url, timeout=timeout_s)
        if resp.status_code == 200:
            data = resp.json()
            lat = float(data.get("latitude") or 0)
            lng = float(data.get("longitude") or 0)
            if lat or lng:
                return {
                    "lat":    lat,
                    "lng":    lng,
                    "label":  f"{data.get('city', '')}, {data.get('country_code', '')}".strip(", "),
                    "source": "ip_auto",
                }
    except Exception:
        pass

    # Attempt 4: ipwhois.app (10k req/month free, HTTPS)
    try:
        url = f"{IPWHOIS_ENDPOINT}{client_ip}" if client_ip else IPWHOIS_ENDPOINT
        resp = requests.get(url, timeout=timeout_s)
        if resp.status_code == 200:
            data = resp.json()
            if data.get("success") is not False:
                lat = float(data.get("latitude") or 0)
                lng = float(data.get("longitude") or 0)
                if lat or lng:
                    return {
                        "lat":    lat,
                        "lng":    lng,
                        "label":  f"{data.get('city', '')}, {data.get('country_code', '')}".strip(", "),
                        "source": "ip_auto",
                    }
    except Exception:
        pass

    print("[location] all IP geolocation APIs failed", file=sys.stderr)
    return None


def get_browser_location() -> Optional[dict]:
    """
    Browser-based GPS via streamlit_js_eval. Works on HTTPS (Streamlit Cloud).
    Async: returns None on the first call; populated dict on subsequent reruns
    once the JS Promise resolves and the user grants permission.
    """
    try:
        from streamlit_js_eval import get_geolocation
    except ImportError:
        return None
    loc = get_geolocation()
    if not loc or "coords" not in loc:
        return None
    lat = loc["coords"].get("latitude")
    lng = loc["coords"].get("longitude")
    if lat is None or lng is None:
        return None
    label = reverse_geocode(float(lat), float(lng)) or "My location"
    return {"lat": float(lat), "lng": float(lng), "label": label, "source": "browser_gps"}


def geocode_address(address: str, api_key: str, timeout_s: float = 3.0) -> Optional[dict]:
    """
    Convert free-text address to lat/lng.
    Tries Google Places API (New) first, then OSM Nominatim fallback.
    """
    if api_key:
        result = _geocode_via_places_api(address, api_key, timeout_s)
        if result is not None:
            return result
    return _geocode_nominatim(address, timeout_s)


def haversine_distance_m(lat1: float, lng1: float, lat2: float, lng2: float) -> float:
    """Return great-circle distance in metres using the Haversine formula."""
    R = 6_371_000.0
    phi1, phi2 = math.radians(lat1), math.radians(lat2)
    dphi = math.radians(lat2 - lat1)
    dlam = math.radians(lng2 - lng1)
    a = math.sin(dphi / 2) ** 2 + math.cos(phi1) * math.cos(phi2) * math.sin(dlam / 2) ** 2
    c = 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))
    return R * c
