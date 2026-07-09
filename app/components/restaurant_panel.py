from __future__ import annotations

import html
import sys
import os
from typing import Optional

import streamlit as st

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from utils.icons import icon


def _fmt_distance(distance_m: float) -> str:
    if distance_m >= 1000:
        return f"{distance_m / 1000:.1f} km"
    return f"{int(distance_m)} m"


def _fmt_price_level(price_level: Optional[int]) -> str:
    return {0: "", 1: icon("dollar", 11), 2: icon("dollar", 11) * 2, 3: icon("dollar", 11) * 3, 4: icon("dollar", 11) * 4}.get(price_level, "")


def _open_badge_html(is_open: Optional[bool]) -> str:
    if is_open is True:
        return (
            '<span style="background:color-mix(in srgb, var(--success) 15%, white); color:var(--success); font-size:10px; '
            'padding:2px 7px; border-radius:var(--radius-pill); font-weight:600;">Open</span>'
        )
    if is_open is False:
        return (
            '<span style="background:var(--surface); color:var(--muted); font-size:10px; '
            'padding:2px 7px; border-radius:var(--radius-pill); font-weight:600;">Closed</span>'
        )
    return ""


def render_restaurant_entry(restaurant: dict) -> None:
    name        = html.escape(restaurant.get("name", ""))
    address_raw = (restaurant.get("address") or "")[:55]
    address     = html.escape(address_raw)
    dist_badge  = _fmt_distance(restaurant.get("distance_m", 0))
    open_badge  = _open_badge_html(restaurant.get("is_open"))
    price       = _fmt_price_level(restaurant.get("price_level"))
    maps_url    = html.escape(restaurant.get("maps_url", "#"))
    rating      = restaurant.get("rating")
    rating_str  = f'{icon("star", 11)} {rating:.1f}' if rating is not None else ""
    source      = restaurant.get("source", "")

    _SOURCE_LABELS = {
        "google_places": "Google Places",
        "here":          "HERE",
        "foursquare":    "Foursquare",
        "osm":           "OpenStreetMap",
    }
    src_display = _SOURCE_LABELS.get(source, "")
    osm_attr = (
        f'<div style="font-size:9px; color:var(--muted); margin-top:4px;">Via {src_display}</div>'
        if src_display else ""
    )

    card_html = (
        '<div style="background:var(--card); border:1px solid var(--border); border-radius:var(--radius-md); '
        'padding:10px 14px; margin:4px 0; box-shadow:var(--shadow-sm);">'
        # Row 1: name + distance badge + open badge
        '<div style="display:flex; justify-content:space-between; align-items:center;">'
        f'<span style="font-size:13px; font-weight:700; color:var(--ink);">{name}</span>'
        '<span>'
        f'<span style="background:var(--brand-tint); color:var(--brand); font-size:10px; '
        f'padding:2px 8px; border-radius:var(--radius-pill); font-weight:600; margin-right:4px;">'
        f'{icon("location", 10)} {dist_badge}</span>'
        f'{open_badge}'
        '</span>'
        '</div>'
        # Row 2: rating + price
        f'<div style="font-size:11px; color:var(--muted); margin-top:3px;">{rating_str} {price}</div>'
        # Row 3: address + maps link
        '<div style="display:flex; justify-content:space-between; align-items:center; margin-top:4px;">'
        f'<span style="font-size:11px; color:var(--muted);">{address}</span>'
        f'<a href="{maps_url}" target="_blank" style="color:var(--brand); font-size:11px; '
        f'text-decoration:none; font-weight:600; white-space:nowrap;">View on Maps →</a>'
        '</div>'
        f'{osm_attr}'
        '</div>'
    )
    st.markdown(card_html, unsafe_allow_html=True)


def render_restaurant_panel(
    fetch_result,
    food_name: str,
    rank: int,
    session_id=None,
    food_id=None,
) -> None:
    with st.expander("Find it near you", icon=":material/location_on:", expanded=(rank == 1)):
        status      = fetch_result.get("status") if fetch_result else "no_key"
        restaurants = fetch_result.get("restaurants", []) if fetch_result else []

        _CAPTION_LABELS = {
            "google_places": "Google Places",
            "here":          "HERE",
            "foursquare":    "Foursquare",
            "osm":           "OpenStreetMap",
        }
        if status == "ok" and restaurants:
            src_label = _CAPTION_LABELS.get(fetch_result.get("source", ""), "Unknown")
            plural = "s" if len(restaurants) > 1 else ""
            st.caption(f"{len(restaurants)} restaurant{plural} found · via {src_label}")

            for r in restaurants:
                render_restaurant_entry(r)
                st.markdown(
                    "<hr style='margin:6px 0; border:none; border-top:1px solid var(--border);'>",
                    unsafe_allow_html=True,
                )

            # Log impressions fire-and-forget
            if session_id is not None:
                for r in restaurants:
                    try:
                        from db.session_logger import log_restaurant_impression
                        log_restaurant_impression(session_id, food_id, r)
                    except Exception:
                        pass

        elif status == "no_results":
            st.caption(f"No nearby restaurants found for {food_name}.")

        elif status == "no_key":
            st.info(
                "Add GOOGLE_PLACES_API_KEY to .env to enable restaurant discovery. "
                "OpenStreetMap fallback may return limited results in some regions.",
                icon=":material/map:",
            )

        elif status == "error":
            st.warning(fetch_result.get("error_msg", "Restaurant lookup failed."))
