"""Multi-source food image URL fetching service.

Priority chain per dish:
  1. DB image_url field (if populated)
  2. TheMealDB dish search (free, high-quality food photos, no API key)
  3. OpenFoodFacts product search API
  4. Wikipedia page images (via full-text search, not exact title)
  5. Wikimedia Commons file search (with document-scan filtering)
"""

from __future__ import annotations

import os
import sys
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from typing import Optional

import requests
import streamlit as st

from config import (
    FOOD_IMAGE_CACHE_TTL,
    OPENFOODFACTS_SEARCH_URL,
    WIKIPEDIA_API_URL,
    WIKIMEDIA_API_URL,
)

_HEADERS = {"User-Agent": "MoodMeal/1.0 (research prototype)"}
_THEMEALDB_SEARCH_URL = "https://www.themealdb.com/api/json/v1/1/search.php"

# Title-level keywords that indicate a Wikimedia file is a scanned document,
# not a food photograph.  Checked against the lower-cased file title.
_WIKIMEDIA_DOC_TERMS = frozenset({
    "bulletin", "usda", "circular", "pamphlet", "handbook", "manual",
    "specification", "publication", "report", "archive", "historic",
    "nutritive_value", "composition_of", "analysis_of", "do_not_assume",
    ".djvu", ".pdf", "chart", "diagram", "map_of", "logo",
})


def _validate_image_url(url: str, timeout_s: float = 4.0) -> bool:
    """Return True if the URL resolves to a valid image resource."""
    if not url or not url.startswith("http"):
        return False
    try:
        resp = requests.head(url, headers=_HEADERS, timeout=timeout_s, allow_redirects=True)
        if resp.status_code == 200 and resp.headers.get("Content-Type", "").startswith("image/"):
            return True
        # Some CDNs reject HEAD — retry with a streaming GET
        resp = requests.get(url, headers=_HEADERS, timeout=timeout_s, stream=True)
        ct = resp.headers.get("Content-Type", "")
        return resp.status_code == 200 and ct.startswith("image/")
    except Exception:
        return False


def _is_likely_document_url(url: str) -> bool:
    """Return True if the URL path suggests a document scan rather than a food photo."""
    url_lower = url.lower()
    return any(term in url_lower for term in _WIKIMEDIA_DOC_TERMS)


def _from_db(image_url: Optional[str]) -> list[str]:
    if image_url and str(image_url).lower().strip() not in ("", "nan", "none", "null"):
        return [str(image_url)]
    return []


def _from_themealdb(name: str, timeout_s: float = 5.0) -> list[str]:
    """Query TheMealDB for dish photos (free, no API key, curated food images)."""
    try:
        resp = requests.get(
            _THEMEALDB_SEARCH_URL,
            params={"s": name},
            headers=_HEADERS,
            timeout=timeout_s,
        )
        if resp.status_code != 200:
            return []
        meals = resp.json().get("meals") or []
        return [m["strMealThumb"] for m in meals if m.get("strMealThumb")]
    except Exception:
        return []


def _from_openfoodfacts(name: str, timeout_s: float = 5.0) -> list[str]:
    try:
        resp = requests.get(
            OPENFOODFACTS_SEARCH_URL,
            params={
                "search_terms": name,
                "action": "process",
                "json": 1,
                "fields": "image_url,image_front_url",
                "page_size": 5,
            },
            headers=_HEADERS,
            timeout=timeout_s,
        )
        if resp.status_code != 200:
            return []
        products = resp.json().get("products", [])
        seen: set[str] = set()
        urls: list[str] = []
        for p in products:
            for field in ("image_front_url", "image_url"):
                u = p.get(field)
                if u and u not in seen:
                    seen.add(u)
                    urls.append(u)
        return urls
    except Exception:
        return []


def _from_wikipedia(name: str, timeout_s: float = 5.0) -> list[str]:
    """Find food-related Wikipedia pages via full-text search, then fetch thumbnails.

    Using a two-step search (instead of direct title lookup) avoids the failure
    mode where the exact dish name doesn't match any Wikipedia article title.
    """
    try:
        # Step 1: full-text search for food-related pages
        search_resp = requests.get(
            WIKIPEDIA_API_URL,
            params={
                "action": "query",
                "list": "search",
                "srsearch": f"{name} food",
                "srlimit": 3,
                "format": "json",
            },
            headers=_HEADERS,
            timeout=timeout_s,
        )
        if search_resp.status_code != 200:
            return []
        search_results = search_resp.json().get("query", {}).get("search", [])
        if not search_results:
            return []

        titles = "|".join(r["title"] for r in search_results[:3])

        # Step 2: fetch page thumbnails for the matched articles
        img_resp = requests.get(
            WIKIPEDIA_API_URL,
            params={
                "action": "query",
                "titles": titles,
                "prop": "pageimages",
                "pithumbsize": 500,
                "format": "json",
            },
            headers=_HEADERS,
            timeout=timeout_s,
        )
        if img_resp.status_code != 200:
            return []

        pages = img_resp.json().get("query", {}).get("pages", {})
        urls: list[str] = []
        for page in pages.values():
            thumb = page.get("thumbnail", {}).get("source")
            if thumb and not _is_likely_document_url(thumb):
                urls.append(thumb)
        return urls
    except Exception:
        return []


def _from_wikimedia_commons(name: str, timeout_s: float = 5.0) -> list[str]:
    """Search Wikimedia Commons for food photos, filtering out document scans."""
    try:
        resp = requests.get(
            WIKIMEDIA_API_URL,
            params={
                "action": "query",
                "list": "search",
                "srsearch": f"{name} food dish",
                "srnamespace": 6,
                "format": "json",
                "srlimit": 15,  # fetch more candidates to account for document filtering
            },
            headers=_HEADERS,
            timeout=timeout_s,
        )
        if resp.status_code != 200:
            return []
        results = resp.json().get("query", {}).get("search", [])
        urls: list[str] = []
        for r in results:
            raw_title = r.get("title", "")
            title = raw_title.replace("File:", "").replace(" ", "_")
            if not title:
                continue
            # Skip file titles that look like scanned documents or non-photo content
            if any(term in title.lower() for term in _WIKIMEDIA_DOC_TERMS):
                continue
            urls.append(
                f"https://commons.wikimedia.org/wiki/Special:FilePath/{title}?width=500"
            )
        return urls
    except Exception:
        return []


@st.cache_data(ttl=FOOD_IMAGE_CACHE_TTL, show_spinner=False)
def fetch_food_images(
    food_name: str,
    image_url_from_db: Optional[str] = None,
    n: int = 3,
) -> list[str]:
    """Return up to n validated image URLs for the given dish name.

    Sources are tried in priority order; collection stops once n valid URLs
    are gathered. Each source failure is silently skipped.
    """
    sources = [
        lambda: _from_db(image_url_from_db),
        lambda: _from_themealdb(food_name),
        lambda: _from_openfoodfacts(food_name),
        lambda: _from_wikipedia(food_name),
        lambda: _from_wikimedia_commons(food_name),
    ]
    collected: list[str] = []
    for source_fn in sources:
        if len(collected) >= n:
            break
        try:
            candidates = source_fn()
            for url in candidates:
                if len(collected) >= n:
                    break
                if url not in collected and _validate_image_url(url):
                    collected.append(url)
        except Exception:
            continue
    return collected
