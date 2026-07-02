"""Food-photo providers behind a single interface. Keys stay server-side."""
from __future__ import annotations

from typing import Protocol, runtime_checkable

import httpx

_SEARCH_URL = "https://www.googleapis.com/customsearch/v1"


@runtime_checkable
class ImageProvider(Protocol):
    enabled: bool

    def images(self, food: str, limit: int = 3) -> list[str]: ...


class NullImageProvider:
    """Used when no image-search key is configured (graceful degradation)."""
    enabled = False

    def images(self, food: str, limit: int = 3) -> list[str]:
        return []


class GoogleImageProvider:
    """Google Custom Search (image mode). Returns up to `limit` photo URLs."""
    enabled = True

    def __init__(self, api_key: str, cx: str, client: httpx.Client | None = None):
        self._api_key = api_key
        self._cx = cx
        self._client = client or httpx.Client(timeout=10.0)

    def images(self, food: str, limit: int = 3) -> list[str]:
        try:
            resp = self._client.get(_SEARCH_URL, params={
                "key": self._api_key,
                "cx": self._cx,
                "q": food,
                "searchType": "image",
                "num": min(limit, 10),
            })
            resp.raise_for_status()
            data = resp.json()
            items = data.get("items", []) if isinstance(data, dict) else []
            if not isinstance(items, list):
                return []
        except (httpx.HTTPError, ValueError):
            return []
        return [it["link"] for it in items if "link" in it][:limit]
