"""
EmoEating design tokens — single source of truth for color/type/spacing.

Every hex value the app uses (CSS custom properties, Plotly figures, inline
HTML strings, the voice-conversation iframe) should trace back to this
module so the visual system can't drift between Python and CSS.
"""

from __future__ import annotations

import os

# ── Brand / neutral palette ───────────────────────────────────────────────────
PALETTE = {
    "brand":        "#34496B",
    "brand_hover":  "#283A58",
    "brand_tint":   "#E7ECF4",
    "ink":          "#1D212E",
    "muted":        "#5E6473",
    "surface":      "#F5F6FA",
    "card":         "#FFFFFF",
    "border":       "#E4E7EE",
    "success":      "#2E9E68",
    "warning":      "#DFA021",
    "danger":       "#D2483E",
    # Chrome tokens — additive; give depth/hierarchy without new hues.
    "ink_soft":     "#3A4152",
    "brand_soft":   "#4E648A",
    "focus":        "#6C8CC7",
    "hairline":     "#EEF0F5",
    "elevate":      "#FBFCFE",
}

# ── Affective-zone palette — 3-step ramp per zone ─────────────────────────────
# core   = AA-legible on white, for text/borders/badges
# accent = original saturated hue, for markers/fills (circumplex, charts)
# tint   = pale panel background
ZONE_PALETTE = {
    "Q1_POS_ACT": {"core": "#B8830E", "accent": "#F4B740", "tint": "#FBF0D5"},
    "Q2_NEG_ACT": {"core": "#C9553A", "accent": "#F0997B", "tint": "#FBE7DF"},
    "Q3_NEG_DEACT": {"core": "#3B77BC", "accent": "#85B7EB", "tint": "#E4EEF8"},
    "NEUTRAL_BASELINE": {"core": "#6A6960", "accent": "#A8A69C", "tint": "#EFEEE9"},
}

# ── Macronutrient colors — distinct from brand + zone hues ────────────────────
MACRO_COLORS = {
    "carb": "#DDA43A",
    "prot": "#2F7D8C",
    "fat":  "#4FB08C",
}

# ── BMI status colors — health-status semantics, distinct from zone/brand hues ─
BMI_STATUS_COLORS = {
    "underweight": "#3B77BC",
    "normal":      "#2E9E68",
    "overweight":  "#DFA021",
    "obese":       "#D2483E",
}

# ── Typography ─────────────────────────────────────────────────────────────────
# Single superfamily (Plex Sans + Plex Mono) — headings differentiate by weight
# and tracking, not by a second display face. See guide.md UI redesign notes.
FONT_BODY    = "'IBM Plex Sans', system-ui, -apple-system, sans-serif"
FONT_DISPLAY = FONT_BODY
FONT_MONO    = "'IBM Plex Mono', 'Fira Code', monospace"

GOOGLE_FONTS_IMPORT_URL = (
    "https://fonts.googleapis.com/css2?"
    "family=IBM+Plex+Sans:wght@400;500;600;700&"
    "family=IBM+Plex+Mono:wght@400;500&"
    "display=swap"
)

# ── Spacing / radius / shadow / motion ────────────────────────────────────────
SPACE = {"1": "4px", "2": "8px", "3": "12px", "4": "16px", "5": "24px", "6": "32px", "7": "48px", "8": "64px"}
RADIUS = {"sm": "6px", "md": "10px", "lg": "14px", "pill": "999px"}
SHADOW = {
    "sm": "0 1px 3px rgba(29, 33, 46, 0.06)",
    "md": "0 4px 12px -2px rgba(29, 33, 46, 0.08)",
    "lg": "0 12px 32px -8px rgba(29, 33, 46, 0.12)",
    "ring": "0 0 0 1px rgba(52, 73, 107, 0.10)",
}
GRADIENT = {
    "brand": "linear-gradient(135deg, #34496B 0%, #283A58 100%)",
    "hero": "linear-gradient(180deg, #FBFCFE 0%, #F5F6FA 100%)",
}
MOTION = {
    "ease": "cubic-bezier(.22, .61, .36, 1)",
    "fast": "120ms",
    "base": "200ms",
    "spring": "cubic-bezier(.34, 1.56, .64, 1)",
}


def _zone_slug(zone_key: str) -> str:
    return {
        "Q1_POS_ACT": "q1",
        "Q2_NEG_ACT": "q2",
        "Q3_NEG_DEACT": "q3",
        "NEUTRAL_BASELINE": "neutral",
    }[zone_key]


def build_root_css() -> str:
    """Emit the `:root { --token: value; }` block consumed by style.css and
    every inline `style=` string across the app (CSS vars resolve inline)."""
    lines = [":root {"]

    for name, value in PALETTE.items():
        lines.append(f"  --{name.replace('_', '-')}: {value};")

    for zone_key, ramp in ZONE_PALETTE.items():
        slug = _zone_slug(zone_key)
        for step, value in ramp.items():
            lines.append(f"  --zone-{slug}-{step}: {value};")

    for macro, value in MACRO_COLORS.items():
        lines.append(f"  --macro-{macro}: {value};")

    lines.append(f"  --font-display: {FONT_DISPLAY};")
    lines.append(f"  --font-body: {FONT_BODY};")
    lines.append(f"  --font-mono: {FONT_MONO};")

    for step, value in SPACE.items():
        lines.append(f"  --space-{step}: {value};")
    for step, value in RADIUS.items():
        lines.append(f"  --radius-{step}: {value};")
    for step, value in SHADOW.items():
        lines.append(f"  --shadow-{step}: {value};")
    for name, value in GRADIENT.items():
        lines.append(f"  --gradient-{name}: {value};")
    for step, value in MOTION.items():
        lines.append(f"  --motion-{step}: {value};")

    lines.append("}")
    return "\n".join(lines)


def inject_global_theme() -> None:
    """Inject design tokens + app/assets/style.css into the current page.

    Must be called from WITHIN each st.Page's script (top of its show()),
    not from main.py before/after st.navigation(...).run() — .run() halts
    further script execution in the entry file, so anything rendered
    before or after it there is silently discarded; it never reaches the
    page actually shown to the user.

    Uses st.html(), not st.markdown(unsafe_allow_html=True) — Streamlit
    sanitizes <style> tags out of markdown-rendered HTML. The <style> body
    is further wrapped in a hidden <div> because a body that is ONLY a
    <style> tag is special-cased by Streamlit
    (streamlit/elements/html.py::_html_only_style_tags) into an ephemeral
    "event" container that never lands in the persistent page DOM — the
    CSS silently never applies. <style> rules apply document-wide
    regardless of their container, so the hidden wrapper costs nothing.
    """
    import streamlit as st

    def _inject(css: str) -> None:
        st.html(f"<div style='display:none'><style>{css}</style></div>")

    _inject(f"@import url('{GOOGLE_FONTS_IMPORT_URL}');\n{build_root_css()}")

    _css_path = os.path.join(os.path.dirname(__file__), "assets", "style.css")
    if os.path.exists(_css_path):
        with open(_css_path) as f:
            _inject(f.read())
