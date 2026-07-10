"""
Inline-SVG icon set for EmoEating's raw-HTML card internals.

Streamlit's native `:material/name:` icon syntax only renders inside
Streamlit-owned widgets (buttons, st.info, nav) — it does not render inside
`st.markdown(unsafe_allow_html=True)` strings, which is where most of the
app's card/badge markup lives. These icons fill that gap.

Every icon is `stroke="currentColor"` / `fill="none"` (or currentColor fills
for the emotion faces) so it inherits the color of its containing element —
wrap usage in a `<span style="color:var(--brand)">{ICON}</span>` or similar.
"""

from __future__ import annotations

_STROKE = 'fill="none" stroke="currentColor" stroke-width="1.75" stroke-linecap="round" stroke-linejoin="round"'


def _svg(inner: str, size: int = 20) -> str:
    return (
        f'<svg width="{size}" height="{size}" viewBox="0 0 24 24" '
        f'xmlns="http://www.w3.org/2000/svg" style="display:inline-block;vertical-align:middle">{inner}</svg>'
    )


# ── UI chrome icons ───────────────────────────────────────────────────────────
ICONS = {
    "mic": _svg(
        f'<rect x="9" y="3" width="6" height="11" rx="3" {_STROKE}/>'
        f'<path d="M5 11a7 7 0 0 0 14 0" {_STROKE}/>'
        f'<line x1="12" y1="18" x2="12" y2="22" {_STROKE}/>'
        f'<line x1="8" y1="22" x2="16" y2="22" {_STROKE}/>'
    ),
    "location": _svg(
        f'<path d="M12 21s-7-6.2-7-11.5A7 7 0 0 1 19 9.5C19 14.8 12 21 12 21z" {_STROKE}/>'
        f'<circle cx="12" cy="9.5" r="2.5" {_STROKE}/>'
    ),
    "star": _svg(
        f'<path d="M12 3.5l2.6 5.6 6 0.8-4.4 4.2 1.1 6-5.3-2.9-5.3 2.9 1.1-6L3.4 9.9l6-0.8L12 3.5z" {_STROKE}/>'
    ),
    "map": _svg(
        f'<path d="M9 4l-6 2v14l6-2 6 2 6-2V4l-6 2-6-2z" {_STROKE}/>'
        f'<line x1="9" y1="4" x2="9" y2="18" {_STROKE}/>'
        f'<line x1="15" y1="6" x2="15" y2="20" {_STROKE}/>'
    ),
    "clock": _svg(
        f'<circle cx="12" cy="12" r="9" {_STROKE}/>'
        f'<path d="M12 7v5l3.5 2" {_STROKE}/>'
    ),
    "leaf": _svg(
        f'<path d="M5 20c0-8 5-14 14-15-1 9-7 14-14 15z" {_STROKE}/>'
        f'<path d="M5 20c3-4 6-7 12-11" {_STROKE}/>'
    ),
    "dollar": _svg(
        f'<line x1="12" y1="2.5" x2="12" y2="21.5" {_STROKE}/>'
        f'<path d="M16.5 6.5c0-1.8-2-3-4.5-3s-4.5 1.2-4.5 3 2 2.5 4.5 3 4.5 1.2 4.5 3-2 3-4.5 3-4.5-1.2-4.5-3" {_STROKE}/>'
    ),
    "check": _svg(f'<path d="M4 12.5l5.5 5.5L20 7" {_STROKE}/>'),
    "info": _svg(
        f'<circle cx="12" cy="12" r="9" {_STROKE}/>'
        f'<line x1="12" y1="11" x2="12" y2="16.5" {_STROKE}/>'
        f'<circle cx="12" cy="7.5" r="0.9" fill="currentColor" stroke="none"/>'
    ),
    "chat": _svg(
        f'<path d="M4 5.5h16v11H9l-4 3.5v-3.5H4z" {_STROKE}/>'
    ),
    "target": _svg(
        f'<circle cx="12" cy="12" r="8.5" {_STROKE}/>'
        f'<circle cx="12" cy="12" r="4.5" {_STROKE}/>'
        f'<circle cx="12" cy="12" r="0.9" fill="currentColor" stroke="none"/>'
    ),
    "vector": _svg(
        f'<line x1="5" y1="19" x2="17" y2="7" {_STROKE}/>'
        f'<path d="M17 7h-5M17 7v5" {_STROKE}/>'
    ),
    "list": _svg(
        f'<circle cx="5" cy="6.5" r="1" fill="currentColor" stroke="none"/>'
        f'<circle cx="5" cy="12" r="1" fill="currentColor" stroke="none"/>'
        f'<circle cx="5" cy="17.5" r="1" fill="currentColor" stroke="none"/>'
        f'<line x1="9" y1="6.5" x2="20" y2="6.5" {_STROKE}/>'
        f'<line x1="9" y1="12" x2="20" y2="12" {_STROKE}/>'
        f'<line x1="9" y1="17.5" x2="20" y2="17.5" {_STROKE}/>'
    ),
    "chevron": _svg(f'<path d="M9 5l7 7-7 7" {_STROKE}/>'),
    "pencil": _svg(
        f'<path d="M4 20l1-4.5L15.5 5 19 8.5 8.5 19 4 20z" {_STROKE}/>'
        f'<line x1="13" y1="7" x2="17" y2="11" {_STROKE}/>'
    ),
    "arrow_right": _svg(
        f'<line x1="4" y1="12" x2="19" y2="12" {_STROKE}/>'
        f'<path d="M13 6l6 6-6 6" {_STROKE}/>'
    ),
    "check_circle": _svg(
        f'<circle cx="12" cy="12" r="9" {_STROKE}/>'
        f'<path d="M8 12.3l2.6 2.6L16.5 9" {_STROKE}/>'
    ),
    "heart": _svg(
        f'<path d="M12 20.2S3.5 15 3.5 8.9A4.4 4.4 0 0 1 12 6.9a4.4 4.4 0 0 1 8.5 2C20.5 15 12 20.2 12 20.2z" {_STROKE}/>'
    ),
    "redo": _svg(
        f'<path d="M4 12a8 8 0 1 1 2.6 5.9" {_STROKE}/>'
        f'<path d="M4 17.5V13h4.5" {_STROKE}/>'
    ),
    "sliders": _svg(
        f'<line x1="5" y1="6" x2="19" y2="6" {_STROKE}/>'
        f'<line x1="5" y1="12" x2="19" y2="12" {_STROKE}/>'
        f'<line x1="5" y1="18" x2="19" y2="18" {_STROKE}/>'
        f'<circle cx="9" cy="6" r="1.8" fill="var(--card,#fff)" stroke="currentColor" stroke-width="1.75"/>'
        f'<circle cx="15" cy="12" r="1.8" fill="var(--card,#fff)" stroke="currentColor" stroke-width="1.75"/>'
        f'<circle cx="10" cy="18" r="1.8" fill="var(--card,#fff)" stroke="currentColor" stroke-width="1.75"/>'
    ),
    "sparkle": _svg(
        f'<path d="M12 3.5l1.4 4.7 4.7 1.4-4.7 1.4-1.4 4.7-1.4-4.7-4.7-1.4 4.7-1.4z" {_STROKE}/>'
        f'<path d="M19 15.5l0.6 2 2 0.6-2 0.6-0.6 2-0.6-2-2-0.6 2-0.6z" {_STROKE}/>'
    ),
}


# ── Emotion face icons ────────────────────────────────────────────────────────
# One consistent 24x24 line-face per EMOTION_COORDS entry (app/config.py),
# replacing raw emoji so faces render tokenized (currentColor) and
# print-consistent across the app and the methodology tables.
_FACE_STROKE = 'fill="none" stroke="currentColor" stroke-width="1.6" stroke-linecap="round" stroke-linejoin="round"'
_FACE_OUTLINE = f'<circle cx="12" cy="12" r="9.5" {_FACE_STROKE}/>'

EMOTION_ICONS = {
    "happy": _svg(
        _FACE_OUTLINE
        + f'<path d="M8.3 10.2q0.6-1 1.2 0" {_FACE_STROKE}/>'
        + f'<path d="M14.5 10.2q0.6-1 1.2 0" {_FACE_STROKE}/>'
        + f'<path d="M8 14.2c1.2 2 6.8 2 8 0" {_FACE_STROKE}/>'
    ),
    "excited": _svg(
        _FACE_OUTLINE
        + f'<path d="M7 9.5l2.4 1.2M11.6 9.5l-2.4 1.2" {_FACE_STROKE}/>'
        + f'<path d="M14.4 9.5l2.4 1.2M19.4 9.5l-2.4 1.2" {_FACE_STROKE}/>'
        + f'<path d="M7.8 14c1 2.6 8.4 2.6 9.4-0.2 0.3-0.8-0.4-1.3-1.1-0.9-2.4 1.3-5 1.3-7.2 0-0.7-0.4-1.4 0.2-1.1 1.1z" {_FACE_STROKE}/>'
    ),
    "content": _svg(
        _FACE_OUTLINE
        + f'<circle cx="9" cy="10.6" r="0.9" fill="currentColor" stroke="none"/>'
        + f'<circle cx="15" cy="10.6" r="0.9" fill="currentColor" stroke="none"/>'
        + f'<path d="M8.5 14.8c1.8 1.2 5.2 1.2 7 0" {_FACE_STROKE}/>'
    ),
    "calm": _svg(
        _FACE_OUTLINE
        + f'<path d="M7.6 10.6q1.2-0.9 2.4 0" {_FACE_STROKE}/>'
        + f'<path d="M14 10.6q1.2-0.9 2.4 0" {_FACE_STROKE}/>'
        + f'<path d="M9.5 15q1.2 0.5 2.5 0.5t2.5-0.5" {_FACE_STROKE}/>'
    ),
    "neutral": _svg(
        _FACE_OUTLINE
        + f'<circle cx="9" cy="10.4" r="0.9" fill="currentColor" stroke="none"/>'
        + f'<circle cx="15" cy="10.4" r="0.9" fill="currentColor" stroke="none"/>'
        + f'<line x1="8.5" y1="15" x2="15.5" y2="15" {_FACE_STROKE}/>'
    ),
    "bored": _svg(
        _FACE_OUTLINE
        + f'<line x1="7.5" y1="10.9" x2="10.5" y2="10.9" {_FACE_STROKE}/>'
        + f'<line x1="13.5" y1="10.9" x2="16.5" y2="10.9" {_FACE_STROKE}/>'
        + f'<path d="M8.5 15.5h7" {_FACE_STROKE}/>'
    ),
    "tired": _svg(
        _FACE_OUTLINE
        + f'<path d="M7.2 11.2q1.4-1.3 2.8 0" {_FACE_STROKE}/>'
        + f'<path d="M14 11.2q1.4-1.3 2.8 0" {_FACE_STROKE}/>'
        + f'<path d="M7.4 13.4q1.1 0.6 2.2 0" {_FACE_STROKE}/>'
        + f'<path d="M14.4 13.4q1.1 0.6 2.2 0" {_FACE_STROKE}/>'
        + f'<ellipse cx="12" cy="16.2" rx="1.6" ry="1" {_FACE_STROKE}/>'
    ),
    "sad": _svg(
        _FACE_OUTLINE
        + f'<path d="M7.5 9.6l2.6 0.9M14.9 10.5l2.6-0.9" {_FACE_STROKE}/>'
        + f'<circle cx="9" cy="11.6" r="0.9" fill="currentColor" stroke="none"/>'
        + f'<circle cx="15" cy="11.6" r="0.9" fill="currentColor" stroke="none"/>'
        + f'<path d="M8.5 16.8q3.5-2 7 0" {_FACE_STROKE}/>'
    ),
    "anxious": _svg(
        _FACE_OUTLINE
        + f'<path d="M7.3 9.3l2.8 1.3M16.7 9.3l-2.8 1.3" {_FACE_STROKE}/>'
        + f'<circle cx="9" cy="11.8" r="1.15" {_FACE_STROKE}/>'
        + f'<circle cx="15" cy="11.8" r="1.15" {_FACE_STROKE}/>'
        + f'<path d="M8.7 16.2c0.6-0.7 1.3 0.7 1.9 0s1.3 0.7 1.9 0 1.3 0.7 1.9 0" {_FACE_STROKE}/>'
        + f'<path d="M18 8.2c0.9 0.8 0.9 1.8 0 2.4-0.9-0.6-0.9-1.6 0-2.4z" {_FACE_STROKE}/>'
    ),
    "stressed": _svg(
        _FACE_OUTLINE
        + f'<path d="M7.2 10.6l2.8-1.6M16.8 10.6l-2.8-1.6" {_FACE_STROKE}/>'
        + f'<line x1="8.2" y1="11.9" x2="9.8" y2="11.9" {_FACE_STROKE}/>'
        + f'<line x1="14.2" y1="11.9" x2="15.8" y2="11.9" {_FACE_STROKE}/>'
        + f'<line x1="11.3" y1="9.6" x2="11" y2="11" {_FACE_STROKE}/>'
        + f'<line x1="12.7" y1="9.6" x2="13" y2="11" {_FACE_STROKE}/>'
        + f'<path d="M9 16.2h6" {_FACE_STROKE}/>'
    ),
    "angry": _svg(
        _FACE_OUTLINE
        + f'<path d="M7.2 9.6l2.9 1.6M16.8 9.6l-2.9 1.6" {_FACE_STROKE}/>'
        + f'<line x1="8" y1="12" x2="10" y2="11.4" {_FACE_STROKE}/>'
        + f'<line x1="14" y1="11.4" x2="16" y2="12" {_FACE_STROKE}/>'
        + f'<path d="M8.3 16.5q3.7-1.6 7.4 0" {_FACE_STROKE}/>'
    ),
}


def _apply_a11y(svg: str, label: str | None) -> str:
    """Mark an icon as meaningful (`role="img"` + `<title>`) or decorative
    (`aria-hidden="true"`). Screen readers otherwise get nothing from these
    inline SVGs — this fixes that in one place for every call site."""
    if label:
        svg = svg.replace("<svg ", '<svg role="img" ', 1)
        idx = svg.index(">") + 1
        svg = svg[:idx] + f"<title>{label}</title>" + svg[idx:]
    else:
        svg = svg.replace("<svg ", '<svg aria-hidden="true" ', 1)
    return svg


def icon(name: str, size: int = 20, color: str | None = None, label: str | None = None) -> str:
    """Return a sized/colored inline-SVG icon by name (from ICONS).

    `label`, when given, renders the icon as a labeled image
    (`role="img"` + `<title>`) for screen readers; omit it (the default)
    for purely decorative icons sitting next to visible text — those get
    `aria-hidden="true"` instead."""
    svg = ICONS.get(name, "")
    if size != 20:
        svg = svg.replace('width="20" height="20"', f'width="{size}" height="{size}"')
    svg = _apply_a11y(svg, label)
    if color:
        return f'<span style="color:{color}">{svg}</span>'
    return svg


def emotion_icon(name: str, size: int = 20, color: str | None = None, label: str | None = None) -> str:
    """Return a sized/colored inline-SVG face icon by emotion name (from EMOTION_ICONS).

    Defaults `label` to the capitalized emotion name (e.g. "Sad") so every
    emotion face is announced to screen readers unless the caller passes
    `label=""` to force it decorative (e.g. when adjacent visible text
    already names the emotion)."""
    svg = EMOTION_ICONS.get(name, "")
    if size != 20:
        svg = svg.replace('width="20" height="20"', f'width="{size}" height="{size}"')
    resolved_label = name.replace("_", " ").capitalize() if label is None else (label or None)
    svg = _apply_a11y(svg, resolved_label)
    if color:
        return f'<span style="color:{color}">{svg}</span>'
    return svg
