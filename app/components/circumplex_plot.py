"""
Interactive Plotly Russell Circumplex plot.
Shows all 11 emotions as labelled dots; highlights selected emotion.
"""

from __future__ import annotations

import plotly.graph_objects as go
import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from config import EMOTION_COORDS


def render_circumplex(selected_emotion: str | None = None) -> go.Figure:
    """
    Return a Plotly Figure of the Russell Circumplex with all 11 emotions.
    selected_emotion: if provided, that point is enlarged and highlighted.
    """
    fig = go.Figure()

    # Background quadrant shading
    quadrant_labels = [
        (0.5,  0.5,  "High V / High A\n(Active Positive)"),
        (-0.5, 0.5,  "Low V / High A\n(Active Negative)"),
        (-0.5, -0.5, "Low V / Low A\n(Passive Negative)"),
        (0.5,  -0.5, "High V / Low A\n(Passive Positive)"),
    ]
    for qx, qy, _ in quadrant_labels:
        fig.add_shape(
            type="rect",
            x0=0, x1=qx * 2 if qx > 0 else qx * 2,
            y0=0, y1=qy * 2 if qy > 0 else qy * 2,
            fillcolor="rgba(200,200,200,0.05)",
            line=dict(width=0),
        )

    # Axis lines
    fig.add_hline(y=0, line=dict(color="#cccccc", width=1, dash="dot"))
    fig.add_vline(x=0, line=dict(color="#cccccc", width=1, dash="dot"))

    # Emotion points
    for emotion, meta in EMOTION_COORDS.items():
        is_selected = emotion == selected_emotion
        size = 22 if is_selected else 12
        border_width = 3 if is_selected else 1
        opacity = 1.0 if is_selected else 0.75

        label = f"{meta['emoji']} {emotion.capitalize()}"
        if is_selected:
            label = f"<b>{label}</b>"

        fig.add_trace(go.Scatter(
            x=[meta["V"]],
            y=[meta["A"]],
            mode="markers+text",
            marker=dict(
                color=meta["color"],
                size=size,
                line=dict(color="#1a1a2e", width=border_width),
                opacity=opacity,
            ),
            text=[label],
            textposition="top center",
            textfont=dict(size=10, color="#1a1a2e"),
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
            font=dict(size=14, color="#1a1a2e"),
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
        height=380,
        margin=dict(l=40, r=20, t=50, b=40),
        paper_bgcolor="#f8f9fa",
        plot_bgcolor="#ffffff",
        font=dict(family="system-ui, sans-serif"),
    )

    return fig
