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
    zone: str = "",
    confidence: Optional[float] = None,
    user_id: Optional[int] = None,
    self_reported_v: Optional[float] = None,
    self_reported_a: Optional[float] = None,
    self_reported_zone: Optional[str] = None,
    db_conn=None,
) -> int:
    """
    Insert a recommendation_sessions row.
    Returns the new session ID (for later selection logging).
    Zone is stored as a prefix in detected_emotion for traceability (e.g. "happy|Q1_POS_ACT").
    self_reported_v/a/zone: participant affect-grid ground truth for Phase 7 zone agreement.
    """
    from db.queries import log_session

    detected = f"{emotion}|{zone}" if zone else emotion

    session_data = {
        "session_token":     session_token,
        "user_id":           user_id,
        "detected_emotion":  detected[:30],
        "emotion_confidence": confidence,
        "emotion_valence":   round(V, 4),
        "emotion_arousal":   round(A, 4),
        "meal_type_filter":  meal_type,
        "recommendations":   [
            {"food_id": r.get("id"), "enms": r.get("enms"), "rank": r.get("rank")}
            for r in recommendations
        ],
        "user_selected_id":  None,
        "self_reported_v":   round(self_reported_v, 4) if self_reported_v is not None else None,
        "self_reported_a":   round(self_reported_a, 4) if self_reported_a is not None else None,
        "self_reported_zone": self_reported_zone,
    }

    return log_session(session_data, db_conn=db_conn)


def log_food_selection(session_id: int, food_id: int, db_conn=None) -> None:
    """Record which food the user chose from the recommendations."""
    from db.queries import log_selection
    log_selection(session_id, food_id, db_conn=db_conn)


def log_restaurant_impression(session_id, food_id, restaurant, db_conn=None) -> None:
    """Fire-and-forget wrapper. Exceptions swallowed by caller."""
    from db.queries import log_restaurant_impression as _log
    _log(session_id, food_id, restaurant, db_conn=db_conn)
