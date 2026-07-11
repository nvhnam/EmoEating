"""
Interactive Plotly Russell Circumplex plot.
Shows all 11 emotions as labelled dots; highlights selected emotion.
"""

from __future__ import annotations

import plotly.graph_objects as go
import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from config import EMOTION_COORDS, ZONE_PALETTE
from theme import PALETTE


def _hex_to_rgba(hex_color: str, alpha: float) -> str:
    hex_color = hex_color.lstrip("#")
    r, g, b = (int(hex_color[i:i + 2], 16) for i in (0, 2, 4))
    return f"rgba({r},{g},{b},{alpha})"


def render_circumplex(selected_emotion: str | None = None, height: int = 380) -> go.Figure:
    """
    Return a Plotly Figure of the Russell Circumplex with all 11 emotions.
    selected_emotion: if provided, that point is enlarged and highlighted.
    """
    fig = go.Figure()

    # Background quadrant shading — tinted by the affective zone each quadrant
    # maps to (config.classify_zone / guide.md zone-merge rule), so the plot
    # itself teaches the zone mapping instead of showing flat neutral panels.
    quadrant_labels = [
        (0.5,  0.5,  "Q1_POS_ACT",       "High V / High A\n(Active Positive)"),
        (-0.5, 0.5,  "Q2_NEG_ACT",       "Low V / High A\n(Active Negative)"),
        (-0.5, -0.5, "Q3_NEG_DEACT",     "Low V / Low A\n(Passive Negative)"),
        (0.5,  -0.5, "NEUTRAL_BASELINE", "High V / Low A\n(Passive Positive)"),
    ]
    for qx, qy, zone_key, _ in quadrant_labels:
        fig.add_shape(
            type="rect",
            x0=0, x1=qx * 2,
            y0=0, y1=qy * 2,
            fillcolor=_hex_to_rgba(ZONE_PALETTE[zone_key]["tint"], 0.55),
            line=dict(width=0),
        )

    # Quadrant text labels — the zone names are otherwise conveyed by tint
    # color alone; a faint label makes each quadrant legible without color
    # (screen readers / colorblind users / greyscale print of the poster).
    for qx, qy, zone_key, quad_text in quadrant_labels:
        fig.add_annotation(
            x=qx, y=qy,
            text=quad_text.replace("\n", "<br>"),
            showarrow=False,
            font=dict(size=9, color=ZONE_PALETTE[zone_key]["core"], family="IBM Plex Sans, sans-serif"),
            opacity=0.85,
            align="center",
        )

    # Axis lines
    fig.add_hline(y=0, line=dict(color=PALETTE["border"], width=1, dash="dot"))
    fig.add_vline(x=0, line=dict(color=PALETTE["border"], width=1, dash="dot"))

    # Emotion points
    for emotion, meta in EMOTION_COORDS.items():
        is_selected = emotion == selected_emotion
        size = 22 if is_selected else 12
        border_width = 3 if is_selected else 1
        opacity = 1.0 if is_selected else 0.75

        label = emotion.capitalize()
        if is_selected:
            label = f"<b>{label}</b>"

        fig.add_trace(go.Scatter(
            x=[meta["V"]],
            y=[meta["A"]],
            mode="markers+text",
            marker=dict(
                color=meta["color"],
                size=size,
                line=dict(color=PALETTE["ink"], width=border_width),
                opacity=opacity,
            ),
            text=[label],
            textposition="top center",
            textfont=dict(size=10, color=PALETTE["ink"], family="IBM Plex Sans, sans-serif"),
            name=emotion,
            hovertemplate=(
                f"<b>{emotion.capitalize()}</b><br>"
                f"Valence: {meta['V']:.2f}<br>"
                f"Arousal: {meta['A']:.2f}<extra></extra>"
            ),
            showlegend=False,
        ))

    fig.update_layout(
        title=dict(
            text="Russell Circumplex Model of Affect",
            font=dict(size=14, color=PALETTE["ink"], family="IBM Plex Sans, sans-serif"),
            x=0.5,
        ),
        xaxis=dict(
            title=dict(text="Valence (Negative ← → Positive)", font=dict(size=11)),
            range=[-1.1, 1.1],
            showgrid=False,
            zeroline=False,
        ),
        yaxis=dict(
            title=dict(text="Arousal (Low ↓ ↑ High)", font=dict(size=11)),
            range=[-1.1, 1.1],
            showgrid=False,
            zeroline=False,
        ),
        height=height,
        autosize=True,
        margin=dict(l=32, r=16, t=44, b=36),
        paper_bgcolor=PALETTE["surface"],
        plot_bgcolor=PALETTE["card"],
        font=dict(family="IBM Plex Sans, sans-serif", color=PALETTE["muted"]),
    )

    return fig
