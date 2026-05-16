"""Collapsible food image gallery component.

Shows a 3-column photo grid inside an expander. Images are fetched from
multiple online sources the first time, then cached in session_state.
"""

from __future__ import annotations

import os
import sys
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from typing import Optional

import streamlit as st

from config import FOOD_IMAGE_COUNT


def render_food_image_gallery(
    food_name: str,
    food_id: int,
    image_url: Optional[str] = None,
) -> None:
    """Render an expandable 3-column image grid for the given dish.

    On first open: fetches images (with a spinner), then caches the result.
    On subsequent opens: renders instantly from session_state cache.
    """
    from services.food_images import fetch_food_images

    cache_key = f"food_images_{food_id}"

    with st.expander(f"View photos of {food_name}"):
        if cache_key in st.session_state:
            urls = st.session_state[cache_key]
        else:
            with st.spinner("Fetching photos..."):
                urls = fetch_food_images(food_name, image_url, FOOD_IMAGE_COUNT, food_id)
            st.session_state[cache_key] = urls

        if not urls:
            st.caption("No photos available for this dish.")
            return

        cols = st.columns(3)
        for i, url in enumerate(urls[:3]):
            try:
                cols[i].image(url, use_container_width=True)
            except Exception:
                cols[i].caption("Image unavailable.")
