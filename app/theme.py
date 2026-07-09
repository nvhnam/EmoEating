"""
EmoEating design tokens — single source of truth for color/type/spacing.

Every hex value the app uses (CSS custom properties, Plotly figures, inline
HTML strings, the voice-conversation iframe) should trace back to this
module so the visual system can't drift between Python and CSS.
"""

from __future__ import annotations

# ── Brand / neutral palette ───────────────────────────────────────────────────
PALETTE = {
    "brand":        "#544AA8",
    "brand_hover":  "#43397F",
    "brand_tint":   "#ECEAF7",
    "ink":          "#211B34",
    "muted":        "#6C6879",
    "surface":      "#FAF8F4",
    "card":         "#FFFFFF",
    "border":       "#EAE6DF",
    "success":      "#2E9E68",
    "warning":      "#DFA021",
    "danger":       "#D2483E",
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
FONT_DISPLAY = "'Space Grotesk', system-ui, -apple-system, sans-serif"
FONT_BODY    = "'IBM Plex Sans', system-ui, -apple-system, sans-serif"
FONT_MONO    = "'IBM Plex Mono', 'Fira Code', monospace"

GOOGLE_FONTS_IMPORT_URL = (
    "https://fonts.googleapis.com/css2?"
    "family=Space+Grotesk:wght@500;600;700&"
    "family=IBM+Plex+Sans:wght@400;500;600;700&"
    "family=IBM+Plex+Mono:wght@400;500&"
    "display=swap"
)

# ── Spacing / radius / shadow / motion ────────────────────────────────────────
SPACE = {"1": "4px", "2": "8px", "3": "12px", "4": "16px", "5": "24px", "6": "32px", "7": "48px", "8": "64px"}
RADIUS = {"sm": "8px", "md": "12px", "lg": "16px", "pill": "999px"}
SHADOW = {
    "sm": "0 1px 3px rgba(33, 27, 52, 0.06)",
    "md": "0 4px 14px -2px rgba(33, 27, 52, 0.10)",
}
MOTION = {"ease": "cubic-bezier(.22, .61, .36, 1)", "fast": "120ms", "base": "200ms"}


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
    for step, value in MOTION.items():
        lines.append(f"  --motion-{step}: {value};")

    lines.append("}")
    return "\n".join(lines)
