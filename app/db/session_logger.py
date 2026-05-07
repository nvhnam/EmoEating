"""
Logs recommendation sessions to the DB.
Called from the recommendations page after computing results.
"""

from __future__ import annotations
from typing import Optional


def log_recommendation_session(
    session_token: str,
    emotion: str,
    meal_type: str,
    recommendations: list[dict],
    V: float,
    A: float,
    confidence: Optional[float] = None,
    user_id: Optional[int] = None,
    db_conn=None,
) -> int:
    """
    Insert a recommendation_sessions row.
    Returns the new session ID (for later selection logging).
    """
    from db.queries import log_session

    session_data = {
        "session_token":     session_token,
        "user_id":           user_id,
        "detected_emotion":  emotion,
        "emotion_confidence": confidence,
        "emotion_valence":   round(V, 4),
        "emotion_arousal":   round(A, 4),
        "meal_type_filter":  meal_type,
        "recommendations":   [
            {"food_id": r.get("id"), "score": r.get("final_score"), "rank": r.get("rank")}
            for r in recommendations
        ],
        "user_selected_id":  None,
    }

    return log_session(session_data, db_conn=db_conn)


def log_food_selection(session_id: int, food_id: int, db_conn=None) -> None:
    """Record which food the user chose from the recommendations."""
    from db.queries import log_selection
    log_selection(session_id, food_id, db_conn=db_conn)
