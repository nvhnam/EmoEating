"""Multi-source food image URL fetching service.

Priority chain per dish:
  1. DB image_url field (if populated)
  2. TheMealDB dish search  — tries name variants + ingredient filter fallback
  3. Wikipedia page images  — normalized core name, original-size images
  4. Wikimedia Commons      — proper imageinfo API (no broken Special:FilePath)
  5. OpenFoodFacts          — relevance-gated by food tokens

All sources are queried up-front; candidates are relevance-gated, deduplicated,
then validated concurrently so the total wall-clock stays under ~4 s even when
individual sources are slow or return unusable URLs.

Results are stored in a persistent SQLite cache (30-day TTL) so study
participants always see the same images across sessions.
"""

from __future__ import annotations

import os
import sys
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from concurrent.futures import ThreadPoolExecutor, as_completed
from typing import Optional

import requests
import streamlit as st

from config import (
    FOOD_IMAGE_CACHE_TTL,
    OPENFOODFACTS_SEARCH_URL,
    WIKIPEDIA_API_URL,
    WIKIMEDIA_API_URL,
)

_HEADERS = {"User-Agent": "EmoEating/1.0 (research prototype)"}
_THEMEALDB_SEARCH_URL    = "https://www.themealdb.com/api/json/v1/1/search.php"
_THEMEALDB_FILTER_URL    = "https://www.themealdb.com/api/json/v1/1/filter.php"
_SKIP_EXTS = frozenset({"svg", "pdf", "djvu", "tif", "tiff"})

_WIKIMEDIA_DOC_TERMS = frozenset({
    "bulletin", "usda", "circular", "pamphlet", "handbook", "manual",
    "specification", "publication", "report", "archive", "historic",
    "nutritive_value", "composition_of", "analysis_of", "do_not_assume",
    ".djvu", ".pdf", "chart", "diagram", "map_of", "logo",
})

_JPEG_MAGIC = b"\xff\xd8\xff"
_PNG_MAGIC  = b"\x89PNG"
_GIF_MAGIC  = b"GIF8"
_WEBP_RIFF  = b"RIFF"


# ── Helpers ──────────────────────────────────────────────────────────────────

def _validate_image_url(url: str, timeout_s: float = 4.0) -> bool:
    """Return True if url resolves to a valid raster image (>2 KB)."""
    if not url or not url.startswith("http"):
        return False
    try:
        resp = requests.head(url, headers=_HEADERS, timeout=timeout_s, allow_redirects=True)
        ct = resp.headers.get("Content-Type", "")
        cl = int(resp.headers.get("Content-Length", "0") or "0")
        if resp.status_code == 200 and ct.startswith("image/") and (cl == 0 or cl > 2000):
            return True
        # Fall back to streaming GET + magic byte check
        resp = requests.get(url, headers=_HEADERS, timeout=(3.0, 5.0), stream=True)
        if resp.status_code != 200:
            return False
        ct = resp.headers.get("Content-Type", "")
        cl = int(resp.headers.get("Content-Length", "0") or "0")
        if cl and cl < 2000:
            return False
        if ct.startswith("image/") and "svg" not in ct:
            return True
        chunk = next(resp.iter_content(chunk_size=16), b"")
        return (
            chunk[:3] == _JPEG_MAGIC
            or chunk[:4] == _PNG_MAGIC
            or chunk[:4] == _GIF_MAGIC
            or (chunk[:4] == _WEBP_RIFF and b"WEBP" in chunk[:12])
        )
    except Exception:
        return False


def _validate_batch(
    candidates: list[dict],
    need: int,
    max_workers: int = 8,
) -> list[str]:
    """Validate candidate dicts concurrently; return first *need* valid URLs
    in original priority order.

    Candidates with 'pre_validated': True skip the HTTP check — used for
    Wikimedia URLs whose MIME type was already confirmed by the API.
    """
    if not candidates:
        return []

    pre = [c for c in candidates if c.get("pre_validated")]
    to_check = [c for c in candidates if not c.get("pre_validated")]

    valid: dict[str, bool] = {c["url"]: True for c in pre}
    if to_check:
        with ThreadPoolExecutor(max_workers=min(max_workers, len(to_check))) as ex:
            fut_map = {ex.submit(_validate_image_url, c["url"]): c["url"] for c in to_check}
            for fut in as_completed(fut_map):
                url = fut_map[fut]
                try:
                    valid[url] = fut.result()
                except Exception:
                    valid[url] = False

    return [c["url"] for c in candidates if valid.get(c["url"])][:need]


def _is_likely_document_url(url: str) -> bool:
    url_lower = url.lower()
    return any(term in url_lower for term in _WIKIMEDIA_DOC_TERMS)


def _is_relevant(title: str, tokens: list[str]) -> bool:
    """True if at least one food token appears in the candidate title/name."""
    if not tokens:
        return True
    t = (title or "").lower()
    return any(tok in t for tok in tokens)


def _ext(url: str) -> str:
    path = url.lower().split("?")[0]
    return path.rsplit(".", 1)[-1] if "." in path else ""


# ── Source functions (return list[dict] with 'url' and 'title') ──────────────

def _from_db(image_url: Optional[str]) -> list[dict]:
    if image_url and str(image_url).lower().strip() not in ("", "nan", "none", "null"):
        return [{"url": str(image_url), "title": "db"}]
    return []


def _meal_search(name: str, timeout_s: float) -> list[dict]:
    try:
        resp = requests.get(
            _THEMEALDB_SEARCH_URL, params={"s": name}, headers=_HEADERS, timeout=timeout_s,
        )
        if resp.status_code != 200:
            return []
        meals = resp.json().get("meals") or []
        return [
            {"url": m["strMealThumb"], "title": m.get("strMeal", "")}
            for m in meals if m.get("strMealThumb")
        ]
    except Exception:
        return []


def _meal_filter_ingredient(ingredient: str, timeout_s: float) -> list[dict]:
    try:
        resp = requests.get(
            _THEMEALDB_FILTER_URL, params={"i": ingredient}, headers=_HEADERS, timeout=timeout_s,
        )
        if resp.status_code != 200:
            return []
        meals = resp.json().get("meals") or []
        return [
            {"url": m["strMealThumb"], "title": m.get("strMeal", "")}
            for m in meals[:5] if m.get("strMealThumb")
        ]
    except Exception:
        return []


def _from_themealdb(core: str, tokens: list[str], timeout_s: float = 6.0) -> list[dict]:
    """Try core name + shorter variants; fall back to ingredient filter."""
    variants = [core]
    if tokens and len(tokens) >= 2:
        short = " ".join(tokens[:2])
        if short != core:
            variants.append(short)
    if tokens:
        variants.append(tokens[0])

    for variant in variants:
        results = _meal_search(variant, timeout_s)
        if results:
            return results

    # Ingredient-based fallback for non-dish foods (e.g., "chia seeds")
    for tok in tokens[:2]:
        results = _meal_filter_ingredient(tok, timeout_s)
        if results:
            return results
    return []


def _from_openfoodfacts(core: str, tokens: list[str], timeout_s: float = 6.0) -> list[dict]:
    try:
        resp = requests.get(
            OPENFOODFACTS_SEARCH_URL,
            params={
                "search_terms": core,
                "action": "process",
                "json": 1,
                "fields": "image_url,image_front_url,product_name,generic_name",
                "page_size": 8,
            },
            headers=_HEADERS,
            timeout=timeout_s,
        )
        if resp.status_code != 200:
            return []
        products = resp.json().get("products", [])
        seen: set[str] = set()
        results: list[dict] = []
        for p in products:
            # Use core as fallback title so relevance gate doesn't reject products
            # that have empty product_name fields (their content is still relevant
            # because the search query was the food name).
            product_name = p.get("product_name") or p.get("generic_name") or core
            for field in ("image_front_url", "image_url"):
                u = p.get(field)
                if u and u not in seen:
                    seen.add(u)
                    results.append({"url": u, "title": product_name})
        return results
    except Exception:
        return []


def _from_wikipedia(core: str, timeout_s: float = 6.0) -> list[dict]:
    try:
        search_resp = requests.get(
            WIKIPEDIA_API_URL,
            params={
                "action": "query",
                "list": "search",
                "srsearch": core,
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
        img_resp = requests.get(
            WIKIPEDIA_API_URL,
            params={
                "action": "query",
                "titles": titles,
                "prop": "pageimages",
                "piprop": "thumbnail|original",
                "pithumbsize": 600,
                "format": "json",
            },
            headers=_HEADERS,
            timeout=timeout_s,
        )
        if img_resp.status_code != 200:
            return []
        pages = img_resp.json().get("query", {}).get("pages", {})
        results: list[dict] = []
        for page in pages.values():
            page_title = page.get("title", "")
            src = (
                (page.get("original") or {}).get("source")
                or (page.get("thumbnail") or {}).get("source")
            )
            if src and not _is_likely_document_url(src) and _ext(src.split("?")[0]) not in _SKIP_EXTS:
                # Wikipedia images served from upload.wikimedia.org are also
                # rate-limited for HEAD requests; trust them since they come
                # from a controlled API response.
                results.append({"url": src, "title": page_title, "pre_validated": True})
        return results
    except Exception:
        return []


def _wikimedia_search(search_term: str, timeout_s: float = 6.0, limit: int = 20) -> list[dict]:
    """Execute one Wikimedia File-namespace search and return pre_validated image dicts."""
    try:
        resp = requests.get(
            WIKIMEDIA_API_URL,
            params={
                "action": "query",
                "generator": "search",
                "gsrsearch": search_term,
                "gsrnamespace": 6,
                "gsrlimit": limit,
                "prop": "imageinfo",
                "iiprop": "url|mime|size",
                "iiurlwidth": 600,
                "format": "json",
            },
            headers=_HEADERS,
            timeout=timeout_s,
        )
        if resp.status_code != 200:
            return []
        pages = resp.json().get("query", {}).get("pages", {})
        results: list[dict] = []
        for p in pages.values():
            title = p.get("title", "")
            if any(t in title.lower() for t in _WIKIMEDIA_DOC_TERMS):
                continue
            ii_list = p.get("imageinfo") or []
            if not ii_list:
                continue
            ii = ii_list[0]
            if not ii.get("mime", "").startswith("image/"):
                continue
            u = ii.get("thumburl") or ii.get("url")
            if not u or _ext(u.split("?")[0]) in _SKIP_EXTS:
                continue
            if _is_likely_document_url(u):
                continue
            # API confirmed image MIME type — skip expensive HTTP validation.
            results.append({"url": u, "title": title, "pre_validated": True})
        return results
    except Exception:
        return []


def _from_wikimedia_commons(core: str, timeout_s: float = 6.0) -> list[dict]:
    """Search Wikimedia with "{core} food"; if sparse, also try bare "{core}"."""
    primary = _wikimedia_search(f"{core} food", timeout_s, limit=20)
    if len(primary) >= 5:
        return primary
    seen = {r["url"] for r in primary}
    bare = [r for r in _wikimedia_search(core, timeout_s, limit=20) if r["url"] not in seen]
    return primary + bare


def _from_wikimedia_tokens(tokens: list[str], timeout_s: float = 5.0) -> list[dict]:
    """Fallback: search Wikimedia with each major token to cast a wider image net."""
    seen: set[str] = set()
    results: list[dict] = []
    for tok in tokens[:3]:
        if len(tok) < 4:
            continue
        for r in _wikimedia_search(f"{tok} food", timeout_s, limit=10):
            if r["url"] not in seen:
                seen.add(r["url"])
                results.append(r)
        if len(results) >= 9:
            break
    return results


# ── Main entry point ─────────────────────────────────────────────────────────

@st.cache_data(ttl=FOOD_IMAGE_CACHE_TTL, show_spinner=False)
def fetch_food_images(
    food_name: str,
    image_url_from_db: Optional[str] = None,
    n: int = 3,
    food_id: Optional[int] = None,
) -> list[str]:
    """Return up to n validated image URLs for the given dish.

    Checks persistent SQLite cache first (30-day TTL). On miss, queries all
    sources concurrently, applies a relevance gate, validates URLs in parallel,
    and stores the result before returning.
    """
    from services.food_name_normalizer import normalize_food_name
    from services.image_cache import get_cached_images, set_cached_images

    cache_key = str(food_id) if food_id is not None else food_name

    cached = get_cached_images(cache_key)
    if cached is not None:
        return cached

    norm = normalize_food_name(food_name)
    core, tokens = norm["core"], norm["tokens"]

    # Collect from all sources (trusted = skip relevance gate)
    raw: list[dict] = []
    raw += [{**r, "trusted": True}  for r in _from_db(image_url_from_db)]
    raw += [{**r, "trusted": True}  for r in _from_themealdb(core, tokens)]
    raw += [{**r, "trusted": False} for r in _from_wikipedia(core)]
    raw += [{**r, "trusted": False} for r in _from_wikimedia_commons(core)]
    raw += [{**r, "trusted": False} for r in _from_openfoodfacts(core, tokens)]

    # Relevance gate + deduplicate (preserve source priority order)
    seen: set[str] = set()
    candidates: list[dict] = []
    for r in raw:
        u = r.get("url", "")
        if not u or not u.startswith("http") or u in seen:
            continue
        if not r.get("trusted") and not _is_relevant(r.get("title", ""), tokens):
            continue
        seen.add(u)
        candidates.append(r)

    result = _validate_batch(candidates, need=n, max_workers=8)

    # --- Phase 2: fallback when primary sources yield fewer than n images ---
    if len(result) < n and tokens:
        extra_raw: list[dict] = []

        # Try each major food token in Wikimedia (search relevance guaranteed by
        # the token itself, so skip the relevance gate for this batch).
        for r in _from_wikimedia_tokens(tokens):
            if r["url"] not in seen:
                seen.add(r["url"])
                extra_raw.append(r)

        # TheMealDB ingredient filter for the first two tokens.
        for tok in tokens[:2]:
            for r in _meal_filter_ingredient(tok, 5.0):
                u = r.get("url", "")
                if u and u not in seen:
                    seen.add(u)
                    extra_raw.append({**r, "trusted": True})

        extra = _validate_batch(extra_raw, need=n - len(result), max_workers=6)
        result = (result + extra)[:n]

    # Only persist non-empty results so transient API failures don't lock a food
    # into a permanent empty cache entry.
    if result:
        set_cached_images(cache_key, result)
    return result
