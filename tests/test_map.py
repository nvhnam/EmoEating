"""
Manual map/restaurant search tester for MoodMeal.

Usage examples:
  # Search by English name, auto-detect location, default 5 km radius
  python tests/test_map.py --dish "Pho"

  # Search by Vietnamese name in Vietnamese mode, custom location
  python tests/test_map.py --dish "Bun bo Hue" --vn --location "Hoan Kiem, Hanoi"

  # Search with specific radius (km)
  python tests/test_map.py --dish "Banh mi" --radius 3 --location "Ho Chi Minh City"

  # Force English mode with custom location
  python tests/test_map.py --dish "Grilled salmon" --location "Hanoi, Vietnam" --radius 2

Output includes:
  - Resolved lat/lng so you can paste into Google Maps to verify the search origin
  - Each result's lat/lng + direct Google Maps link
  - R-score breakdown (proximity, rating, availability)
  - The exact query string sent to the API
"""

from __future__ import annotations

import argparse
import math
import os
import sys
import time
from typing import Optional

# Force UTF-8 output on Windows so Vietnamese characters print correctly
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")
if hasattr(sys.stderr, "reconfigure"):
    sys.stderr.reconfigure(encoding="utf-8")

import requests

# ---------------------------------------------------------------------------
# Path setup — allow importing from app/ without installing the package
# ---------------------------------------------------------------------------
_TESTS_DIR   = os.path.dirname(os.path.abspath(__file__))
_PROJECT_DIR = os.path.dirname(_TESTS_DIR)
_APP_DIR     = os.path.join(_PROJECT_DIR, "app")
sys.path.insert(0, _APP_DIR)
sys.path.insert(0, _PROJECT_DIR)

from dotenv import load_dotenv
load_dotenv(os.path.join(_PROJECT_DIR, ".env"))

# Import after path / env setup
from config import (
    GOOGLE_PLACES_API_KEY,
    GOOGLE_PLACES_TEXT_SEARCH_URL,
    FOURSQUARE_API_KEY,
    FOURSQUARE_SEARCH_URL,
    HERE_API_KEY,
    HERE_SEARCH_URL,
    OSM_OVERPASS_URL,
    RESTAURANT_SCORE_WEIGHTS,
    USE_VN_DATA,
)

# Colours for terminal output (degrades gracefully on Windows without ANSI)
_GREEN  = "\033[92m"
_YELLOW = "\033[93m"
_CYAN   = "\033[96m"
_RED    = "\033[91m"
_BOLD   = "\033[1m"
_RESET  = "\033[0m"


# ---------------------------------------------------------------------------
# Standalone IP geolocation (no Streamlit dependency)
# ---------------------------------------------------------------------------

def _ip_locate(timeout_s: float = 5.0) -> Optional[dict]:
    """Auto-detect location from public IP via ipapi.co → ipinfo.io fallback."""
    for url, parser in [
        (
            "https://ipapi.co/json/",
            lambda d: {
                "lat":    float(d["latitude"]),
                "lng":    float(d["longitude"]),
                "label":  f"{d.get('city','?')}, {d.get('country_code','?')}",
                "source": "ipapi.co",
            } if not d.get("error") else None,
        ),
        (
            "https://ipinfo.io/json",
            lambda d: {
                "lat":    float(d["loc"].split(",")[0]),
                "lng":    float(d["loc"].split(",")[1]),
                "label":  f"{d.get('city','')}, {d.get('country','')}".strip(", "),
                "source": "ipinfo.io",
            } if "loc" in d and "," in d.get("loc", "") else None,
        ),
    ]:
        try:
            resp = requests.get(url, timeout=timeout_s)
            if resp.status_code == 200:
                result = parser(resp.json())
                if result:
                    return result
        except Exception:
            continue
    return None


# ---------------------------------------------------------------------------
# Geocoding
# ---------------------------------------------------------------------------

def _geocode_google(address: str, api_key: str, timeout_s: float = 5.0) -> Optional[dict]:
    try:
        headers = {
            "X-Goog-Api-Key": api_key,
            "X-Goog-FieldMask": "places.location,places.formattedAddress,places.displayName",
        }
        body = {"textQuery": address, "maxResultCount": 1, "languageCode": "en"}
        resp = requests.post(GOOGLE_PLACES_TEXT_SEARCH_URL, json=body, headers=headers, timeout=timeout_s)
        if resp.status_code != 200:
            return None
        places = resp.json().get("places", [])
        if not places:
            return None
        loc = places[0].get("location", {})
        lat, lng = loc.get("latitude"), loc.get("longitude")
        if lat is None:
            return None
        label = places[0].get("formattedAddress") or address
        return {"lat": float(lat), "lng": float(lng), "label": label, "source": "Google Places"}
    except Exception:
        return None


def _geocode_nominatim(address: str, timeout_s: float = 5.0) -> Optional[dict]:
    try:
        resp = requests.get(
            "https://nominatim.openstreetmap.org/search",
            params={"q": address, "format": "json", "limit": 1},
            headers={"User-Agent": "MoodMeal-test/1.0"},
            timeout=timeout_s,
        )
        if resp.status_code != 200 or not resp.json():
            return None
        r = resp.json()[0]
        return {
            "lat":    float(r["lat"]),
            "lng":    float(r["lon"]),
            "label":  r.get("display_name", address),
            "source": "OSM Nominatim",
        }
    except Exception:
        return None


def resolve_location(address: Optional[str]) -> Optional[dict]:
    if address:
        print(f"  Geocoding '{address}' ...")
        loc = _geocode_google(address, GOOGLE_PLACES_API_KEY) if GOOGLE_PLACES_API_KEY else None
        if not loc:
            loc = _geocode_nominatim(address)
        return loc
    else:
        print("  No location provided — auto-detecting via IP ...")
        return _ip_locate()


# ---------------------------------------------------------------------------
# Haversine
# ---------------------------------------------------------------------------

def haversine_m(lat1: float, lng1: float, lat2: float, lng2: float) -> float:
    R = 6_371_000.0
    phi1, phi2 = math.radians(lat1), math.radians(lat2)
    dphi = math.radians(lat2 - lat1)
    dlam = math.radians(lng2 - lng1)
    a = math.sin(dphi / 2) ** 2 + math.cos(phi1) * math.cos(phi2) * math.sin(dlam / 2) ** 2
    return R * 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))


# ---------------------------------------------------------------------------
# R-score
# ---------------------------------------------------------------------------

def r_score(dist_m: float, radius_m: float, rating: Optional[float], is_open: Optional[bool]) -> float:
    w = RESTAURANT_SCORE_WEIGHTS
    proximity    = max(0.0, min(1.0, 1.0 - dist_m / radius_m))
    rating_norm  = (rating if rating is not None else 3.5) / 5.0
    availability = 1.0 if is_open else 0.5
    return w["alpha"] * proximity + w["beta"] * rating_norm + w["gamma"] * availability


# ---------------------------------------------------------------------------
# Google Places search
# ---------------------------------------------------------------------------

_PRICE_MAP = {
    "PRICE_LEVEL_FREE": 0, "PRICE_LEVEL_INEXPENSIVE": 1,
    "PRICE_LEVEL_MODERATE": 2, "PRICE_LEVEL_EXPENSIVE": 3,
    "PRICE_LEVEL_VERY_EXPENSIVE": 4,
}

_PRICE_DISPLAY = {0: "Free", 1: "$", 2: "$$", 3: "$$$", 4: "$$$$"}


def _search_google(query: str, lat: float, lng: float, radius_m: int,
                   language_code: str, max_results: int = 10) -> list[dict]:
    if not GOOGLE_PLACES_API_KEY:
        return []
    try:
        headers = {
            "X-Goog-Api-Key":   GOOGLE_PLACES_API_KEY,
            "X-Goog-FieldMask": (
                "places.id,places.displayName,places.formattedAddress,"
                "places.location,places.rating,places.priceLevel,"
                "places.regularOpeningHours,places.googleMapsUri"
            ),
        }
        body = {
            "textQuery":      query,
            "maxResultCount": max_results,
            "languageCode":   language_code,
            "locationBias": {
                "circle": {
                    "center": {"latitude": lat, "longitude": lng},
                    "radius": float(radius_m),
                }
            },
        }
        resp = requests.post(GOOGLE_PLACES_TEXT_SEARCH_URL, headers=headers, json=body, timeout=8)
        if resp.status_code != 200:
            print(f"  {_RED}Google Places returned HTTP {resp.status_code}: {resp.text[:200]}{_RESET}")
            return []
        results = []
        for place in resp.json().get("places", []):
            loc      = place.get("location", {})
            p_lat    = float(loc.get("latitude", 0))
            p_lng    = float(loc.get("longitude", 0))
            dist_m   = haversine_m(lat, lng, p_lat, p_lng)
            raw_p    = place.get("priceLevel")
            price    = _PRICE_MAP.get(raw_p) if raw_p else None
            opening  = place.get("regularOpeningHours", {})
            is_open  = opening.get("openNow") if opening else None
            rating   = float(place["rating"]) if place.get("rating") is not None else None
            maps_url = place.get("googleMapsUri") or f"https://maps.google.com/?q={p_lat},{p_lng}"
            results.append({
                "source":    "google_places",
                "name":      place.get("displayName", {}).get("text", "?"),
                "address":   place.get("formattedAddress", ""),
                "lat":       p_lat,
                "lng":       p_lng,
                "dist_m":    dist_m,
                "rating":    rating,
                "price":     price,
                "is_open":   is_open,
                "maps_url":  maps_url,
                "place_id":  place.get("id", ""),
            })
        return results
    except Exception as exc:
        print(f"  {_RED}Google Places error: {exc}{_RESET}")
        return []


# ---------------------------------------------------------------------------
# Foursquare Places search
# ---------------------------------------------------------------------------

def _search_foursquare(query: str, lat: float, lng: float, radius_m: int,
                       max_results: int = 10) -> list[dict]:
    if not FOURSQUARE_API_KEY:
        return []
    try:
        headers = {
            "Authorization": f"Bearer {FOURSQUARE_API_KEY}",
            "Accept":        "application/json",
            "X-Places-Api-Version": "2025-06-17",
            "X-Users-Api-Version": "2025-06-17"
        }
        params = {
            "query":  query,
            "ll":     f"{lat},{lng}",
            "radius": radius_m,
            "limit":  min(max_results, 50),
        }
        resp = requests.get(FOURSQUARE_SEARCH_URL, headers=headers, params=params, timeout=8)
        if resp.status_code != 200:
            print(f"  {_RED}Foursquare HTTP {resp.status_code}: {resp.text[:200]}{_RESET}")
            return []
        results = []
        for venue in resp.json().get("results", []):
            # New API: lat/lng are top-level fields (not nested under geocodes)
            v_lat  = float(venue.get("latitude", 0))
            v_lng  = float(venue.get("longitude", 0))
            dist_m = float(venue.get("distance") or haversine_m(lat, lng, v_lat, v_lng))
            loc    = venue.get("location") or {}
            results.append({
                "source":   "foursquare",
                "name":     venue.get("name", "?"),
                "address":  loc.get("formatted_address") or loc.get("address") or "",
                "lat":      v_lat,
                "lng":      v_lng,
                "dist_m":   dist_m,
                "rating":   None,   # not returned by new endpoint
                "price":    None,
                "is_open":  None,   # not returned by new endpoint
                "maps_url": f"https://www.google.com/maps/search/?api=1&query={v_lat},{v_lng}",
                "place_id": f"fsq_{venue.get('fsq_place_id','')}",
            })
        return results
    except Exception as exc:
        print(f"  {_RED}Foursquare error: {exc}{_RESET}")
        return []


# ---------------------------------------------------------------------------
# HERE Geocoding & Search
# ---------------------------------------------------------------------------

def _search_here(query: str, lat: float, lng: float, radius_m: int,
                 max_results: int = 10) -> list[dict]:
    if not HERE_API_KEY:
        return []
    try:
        params = {
            "q":      query,
            "in":     f"circle:{lat},{lng};r={radius_m}",
            "limit":  min(max_results, 100),
            "apiKey": HERE_API_KEY,
        }
        resp = requests.get(HERE_SEARCH_URL, params=params, timeout=8)
        if resp.status_code != 200:
            print(f"  {_RED}HERE HTTP {resp.status_code}: {resp.text[:200]}{_RESET}")
            return []
        results = []
        for item in resp.json().get("items", []):
            pos    = item.get("position", {})
            i_lat  = float(pos.get("lat", 0))
            i_lng  = float(pos.get("lng", 0))
            dist_m = float(item.get("distance") or haversine_m(lat, lng, i_lat, i_lng))
            hours  = item.get("openingHours") or []
            is_open = hours[0].get("isOpen") if hours else None
            addr   = item.get("address", {}).get("label", "")
            results.append({
                "source":   "here",
                "name":     item.get("title", "?"),
                "address":  addr,
                "lat":      i_lat,
                "lng":      i_lng,
                "dist_m":   dist_m,
                "rating":   None,   # not available on free tier
                "price":    None,
                "is_open":  is_open,
                "maps_url": f"https://www.google.com/maps/search/?api=1&query={i_lat},{i_lng}",
                "place_id": f"here_{item.get('id','')}",
            })
        return results
    except Exception as exc:
        print(f"  {_RED}HERE error: {exc}{_RESET}")
        return []


# ---------------------------------------------------------------------------
# OSM Overpass search
# ---------------------------------------------------------------------------

def _search_osm(dish_name: str, lat: float, lng: float, radius_m: int,
                max_results: int = 10) -> list[dict]:
    try:
        fetch = max_results * 5
        query = (
            f"[out:json][timeout:10];\n"
            f"(\n"
            f'  node["amenity"="restaurant"](around:{radius_m},{lat},{lng});\n'
            f'  way["amenity"="restaurant"](around:{radius_m},{lat},{lng});\n'
            f");\n"
            f"out center {fetch};"
        )
        resp = requests.post(OSM_OVERPASS_URL, data={"data": query}, timeout=12)
        if resp.status_code != 200:
            return []
        elements = resp.json().get("elements", [])
        results = []
        for el in elements:
            if el.get("type") == "node":
                e_lat, e_lng = el.get("lat", 0.0), el.get("lon", 0.0)
            elif el.get("type") == "way":
                c = el.get("center", {})
                e_lat, e_lng = c.get("lat", 0.0), c.get("lon", 0.0)
            else:
                continue
            tags   = el.get("tags", {})
            dist_m = haversine_m(lat, lng, e_lat, e_lng)
            results.append({
                "source":   "osm",
                "name":     tags.get("name", "Unknown"),
                "address":  tags.get("addr:street", ""),
                "lat":      e_lat,
                "lng":      e_lng,
                "dist_m":   dist_m,
                "rating":   None,
                "price":    None,
                "is_open":  None,
                "maps_url": f"https://www.google.com/maps/search/?api=1&query={e_lat},{e_lng}",
                "place_id": f"osm_{el.get('id',0)}",
            })
        results.sort(key=lambda r: r["dist_m"])
        return results[:max_results]
    except Exception as exc:
        print(f"  {_RED}OSM error: {exc}{_RESET}")
        return []


# ---------------------------------------------------------------------------
# Output helpers
# ---------------------------------------------------------------------------

def _open_label(is_open: Optional[bool]) -> str:
    if is_open is True:
        return f"{_GREEN}Open{_RESET}"
    if is_open is False:
        return f"{_RED}Closed{_RESET}"
    return "Unknown"


def _fmt_dist(m: float) -> str:
    return f"{m:.0f} m" if m < 1000 else f"{m / 1000:.2f} km"


def _google_maps_verify_url(lat: float, lng: float) -> str:
    return f"https://www.google.com/maps/@{lat},{lng},15z"


def _print_result(i: int, r: dict, radius_m: float) -> None:
    score = r_score(r["dist_m"], radius_m, r["rating"], r["is_open"])
    price_str = _PRICE_DISPLAY.get(r["price"], "?") if r["price"] is not None else "—"
    rating_str = f"{r['rating']:.1f}★" if r["rating"] is not None else "no rating"

    print(f"\n  {_BOLD}#{i}  {r['name']}{_RESET}")
    print(f"      Address  : {r['address'] or '(no address in data)'}")
    print(f"      Lat/Lng  : {r['lat']:.6f}, {r['lng']:.6f}")
    print(f"      Distance : {_fmt_dist(r['dist_m'])}")
    print(f"      Rating   : {rating_str}   Price: {price_str}   Status: {_open_label(r['is_open'])}")
    print(f"      R-score  : {score:.4f}  "
          f"(proximity={max(0.0,1-r['dist_m']/radius_m):.3f}, "
          f"rating={(r['rating'] or 3.5)/5:.3f}, "
          f"avail={1.0 if r['is_open'] else 0.5})")
    print(f"      Source   : {r['source']}  |  place_id: {r['place_id']}")
    print(f"      {_CYAN}Maps link: {r['maps_url']}{_RESET}")


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main() -> None:
    parser = argparse.ArgumentParser(
        description="Test the MoodMeal restaurant finder from the command line.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=__doc__,
    )
    parser.add_argument("--dish",     required=True,
                        help="Dish name to search for (English or Vietnamese)")
    parser.add_argument("--location", default=None,
                        help="Your location as free text (e.g. 'Hoan Kiem, Hanoi'). "
                             "Omit to auto-detect via IP.")
    parser.add_argument("--radius",   type=float, default=5.0,
                        help="Search radius in kilometres (default: 5)")
    parser.add_argument("--vn",       action="store_true",
                        help="Use Vietnamese mode: searches with 'nhà hàng' suffix "
                             "and languageCode=vi. Implied automatically when USE_VN_DATA=true in .env.")
    parser.add_argument("--lang",     choices=["en", "vi"], default=None,
                        help="Override language code sent to Google Places (en or vi). "
                             "Defaults to 'vi' in VN mode, 'en' otherwise.")
    parser.add_argument("--no-google",     action="store_true",
                        help="Skip Google Places API.")
    parser.add_argument("--no-foursquare", action="store_true",
                        help="Skip Foursquare Places API.")
    parser.add_argument("--no-here",       action="store_true",
                        help="Skip HERE Geocoding & Search API.")
    parser.add_argument("--max",      type=int, default=8,
                        help="Maximum results to fetch (default: 8)")
    args = parser.parse_args()

    # Resolve flags
    vn_mode       = args.vn or USE_VN_DATA
    language_code = args.lang or ("vi" if vn_mode else "en")
    radius_m      = int(args.radius * 1000)
    dish          = args.dish

    # Build query
    query = f"{dish} nhà hàng" if vn_mode else f"{dish} dish"

    # ── Header ────────────────────────────────────────────────────────────
    print(f"\n{_BOLD}{'─'*60}")
    print(f"  MoodMeal Restaurant Finder — Manual Test")
    print(f"{'─'*60}{_RESET}")
    print(f"  Dish        : {_BOLD}{dish}{_RESET}")
    print(f"  Search query: {_YELLOW}{query}{_RESET}")
    print(f"  Language    : {language_code}   VN mode: {vn_mode}")
    print(f"  Radius      : {args.radius} km  ({radius_m} m)")
    print(f"  Google key  : {'present (' + GOOGLE_PLACES_API_KEY[:8] + '...)' if GOOGLE_PLACES_API_KEY else _YELLOW + 'not set' + _RESET}")
    print(f"  FSQ key     : {'present (' + FOURSQUARE_API_KEY[:8] + '...)' if FOURSQUARE_API_KEY else _YELLOW + 'not set' + _RESET}")
    print(f"  HERE key    : {'present (' + HERE_API_KEY[:8] + '...)' if HERE_API_KEY else _YELLOW + 'not set' + _RESET}")

    # ── Resolve location ──────────────────────────────────────────────────
    print(f"\n{_BOLD}[ Location ]{_RESET}")
    loc = resolve_location(args.location)
    if loc is None:
        print(f"  {_RED}Could not resolve location. Provide --location 'your city' manually.{_RESET}")
        sys.exit(1)

    lat, lng = loc["lat"], loc["lng"]
    print(f"  {_GREEN}Resolved: {loc['label']}{_RESET}")
    print(f"  Lat/Lng : {_BOLD}{lat:.6f}, {lng:.6f}{_RESET}  (via {loc['source']})")
    print(f"  {_CYAN}Verify on map: {_google_maps_verify_url(lat, lng)}{_RESET}")

    # ── Google Places ─────────────────────────────────────────────────────
    if not args.no_google:
        print(f"\n{_BOLD}[ Google Places API (New) ]{_RESET}")
        if not GOOGLE_PLACES_API_KEY:
            print(f"  {_YELLOW}GOOGLE_PLACES_API_KEY not set in .env — skipping.{_RESET}")
        else:
            t0 = time.time()
            gresults = _search_google(query, lat, lng, radius_m, language_code, args.max)
            elapsed  = (time.time() - t0) * 1000
            print(f"  Query   : '{query}'  (languageCode={language_code})")
            print(f"  Returned: {len(gresults)} result(s)  ({elapsed:.0f} ms)")
            if gresults:
                gresults.sort(key=lambda r: -r_score(r["dist_m"], radius_m, r["rating"], r["is_open"]))
                for i, r in enumerate(gresults, 1):
                    _print_result(i, r, radius_m)
            else:
                print(f"  {_YELLOW}No results returned.")
                print(f"  Common causes of Google 403 PERMISSION_DENIED:")
                print(f"    1. API key has HTTP-referrer or IP restrictions — remove them for local testing")
                print(f"       GCP Console → APIs & Services → Credentials → your key → Application restrictions")
                print(f"    2. 'Places API (New)' not enabled — must be the NEW version, not the legacy one")
                print(f"       GCP Console → APIs & Services → Enabled APIs → search 'Places API (New)'")
                print(f"    3. Billing account not active (even free-tier quota requires billing enabled)")
                print(f"  {_RESET}Try HERE (set HERE_API_KEY in .env and re-run, or use --no-google).")

    # ── Foursquare ────────────────────────────────────────────────────────
    if not args.no_foursquare:
        print(f"\n{_BOLD}[ Foursquare Places API (places-api.foursquare.com) ]{_RESET}")
        if not FOURSQUARE_API_KEY:
            print(f"  {_YELLOW}FOURSQUARE_API_KEY not set in .env — skipping.")
            print(f"  Get a free key at: https://foursquare.com/developers/  → Create app → API Key{_RESET}")
        else:
            t0       = time.time()
            fresults = _search_foursquare(query, lat, lng, radius_m, args.max)
            elapsed  = (time.time() - t0) * 1000
            print(f"  Query   : '{query}'")
            print(f"  Returned: {len(fresults)} result(s)  ({elapsed:.0f} ms)")
            if fresults:
                fresults.sort(key=lambda r: -r_score(r["dist_m"], radius_m, r["rating"], r["is_open"]))
                for i, r in enumerate(fresults, 1):
                    _print_result(i, r, radius_m)
            else:
                print(f"  {_YELLOW}No results — try a broader dish name or larger radius.{_RESET}")

    # ── HERE Geocoding & Search ───────────────────────────────────────────
    if not args.no_here:
        print(f"\n{_BOLD}[ HERE Geocoding & Search API ]{_RESET}")
        if not HERE_API_KEY:
            print(f"  {_YELLOW}HERE_API_KEY not set in .env — skipping.")
            print(f"  Get a free key (1 000 req/day, no credit card) at:")
            print(f"  https://platform.here.com/  → Create project → Generate API key{_RESET}")
        else:
            t0       = time.time()
            hresults = _search_here(query, lat, lng, radius_m, args.max)
            elapsed  = (time.time() - t0) * 1000
            print(f"  Query   : '{query}'")
            print(f"  Returned: {len(hresults)} result(s)  ({elapsed:.0f} ms)")
            if hresults:
                hresults.sort(key=lambda r: -r_score(r["dist_m"], radius_m, r["rating"], r["is_open"]))
                for i, r in enumerate(hresults, 1):
                    _print_result(i, r, radius_m)
            else:
                print(f"  {_YELLOW}No results — try a broader dish name or larger radius.{_RESET}")

    # ── OSM Overpass ──────────────────────────────────────────────────────
    print(f"\n{_BOLD}[ OSM Overpass (always-free geographic fallback) ]{_RESET}")
    print(f"  Fuzzy matching dish name '{dish}' against OSM restaurant tags ...")
    t0       = time.time()
    oresults = _search_osm(dish, lat, lng, radius_m, args.max)
    elapsed  = (time.time() - t0) * 1000
    print(f"  Returned: {len(oresults)} result(s)  ({elapsed:.0f} ms)")
    if oresults:
        for i, r in enumerate(oresults, 1):
            _print_result(i, r, radius_m)
    else:
        print(f"  {_YELLOW}No OSM results. OSM coverage may be sparse in this area.{_RESET}")

    # ── Summary ───────────────────────────────────────────────────────────
    print(f"\n{_BOLD}{'─'*60}")
    print(f"  Summary")
    print(f"{'─'*60}{_RESET}")
    print(f"  Search origin : {lat:.6f}, {lng:.6f}")
    print(f"  Verify origin : {_google_maps_verify_url(lat, lng)}")
    print(f"  Query used    : {query}  (languageCode={language_code})")
    print(f"  Providers     : Google Places → Foursquare → HERE → OSM Overpass (first non-empty wins in app)")
    print(f"  Paste any lat/lng pair above into https://maps.google.com to confirm placement.")
    print()


if __name__ == "__main__":
    main()
