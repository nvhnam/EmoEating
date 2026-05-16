"""Multi-source food image URL fetching service.

Priority chain per dish:
  1. DB image_url field (if populated)
  2. OpenFoodFacts product search API
  3. Wikipedia page images API
  4. Wikimedia Commons file search
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


def _from_db(image_url: Optional[str]) -> list[str]:
    if image_url and str(image_url).lower().strip() not in ("", "nan", "none", "null"):
        return [str(image_url)]
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
    try:
        resp = requests.get(
            WIKIPEDIA_API_URL,
            params={
                "action": "query",
                "titles": name,
                "prop": "pageimages",
                "pithumbsize": 500,
                "format": "json",
            },
            headers=_HEADERS,
            timeout=timeout_s,
        )
        if resp.status_code != 200:
            return []
        pages = resp.json().get("query", {}).get("pages", {})
        urls: list[str] = []
        for page in pages.values():
            thumb = page.get("thumbnail", {}).get("source")
            if thumb:
                urls.append(thumb)
        return urls
    except Exception:
        return []


def _from_wikimedia_commons(name: str, timeout_s: float = 5.0) -> list[str]:
    try:
        resp = requests.get(
            WIKIMEDIA_API_URL,
            params={
                "action": "query",
                "list": "search",
                "srsearch": f"{name} food dish",
                "srnamespace": 6,
                "format": "json",
                "srlimit": 5,
            },
            headers=_HEADERS,
            timeout=timeout_s,
        )
        if resp.status_code != 200:
            return []
        results = resp.json().get("query", {}).get("search", [])
        urls: list[str] = []
        for r in results:
            title = r.get("title", "").replace("File:", "").replace(" ", "_")
            if title:
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
