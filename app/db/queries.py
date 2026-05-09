"""
All SQL queries as typed functions.
Uses SQLAlchemy connection from connection.py.
"""

from __future__ import annotations
from typing import Optional
import json

from sqlalchemy import text


def _conn(db_conn=None):
    if db_conn is not None:
        return db_conn
    from db.connection import get_connection
    return get_connection()


_USER_TO_DB_MEAL_TYPE = {
    "breakfast":    "complete_meal",
    "lunch":        "complete_meal",
    "dinner":       "complete_meal",
    "complete_meal":"complete_meal",
    "snack":        "snack",
    "beverage":     "beverage",
}


def get_meals(
    meal_type: str,
    dietary_restrictions: Optional[list[str]] = None,
    min_completeness: int = 5,
    kcal_min: Optional[float] = None,
    kcal_max: Optional[float] = None,
    limit: int = 2000,
    db_conn=None,
) -> list[dict]:
    """
    Fetch candidate meals from meals_with_nutrients view.
    Applies dietary filters and caloric range if specified.
    Returns up to `limit` rows.
    """
    restrictions = dietary_restrictions or []
    db_meal_type = _USER_TO_DB_MEAL_TYPE.get(meal_type, "complete_meal")

    conditions = [
        "meal_type = :meal_type",
        "data_completeness >= :min_completeness",
    ]
    params: dict = {
        "meal_type":        db_meal_type,
        "min_completeness": min_completeness,
        "limit":            limit,
    }

    if kcal_min is not None:
        conditions.append("calories_kcal >= :kcal_min")
        params["kcal_min"] = kcal_min
    if kcal_max is not None:
        conditions.append("calories_kcal <= :kcal_max")
        params["kcal_max"] = kcal_max
    if "vegetarian" in [r.lower() for r in restrictions]:
        conditions.append("is_vegetarian = 1")
    if "vegan" in [r.lower() for r in restrictions]:
        conditions.append("is_vegan = 1")
    if "gluten-free" in [r.lower() for r in restrictions] or "gluten_free" in [r.lower() for r in restrictions]:
        conditions.append("is_gluten_free = 1")
    if "dairy-free" in [r.lower() for r in restrictions] or "dairy_free" in [r.lower() for r in restrictions]:
        conditions.append("is_dairy_free = 1")

    where = " AND ".join(conditions)
    sql = f"""
        SELECT *
        FROM meals_with_nutrients
        WHERE {where}
        ORDER BY data_completeness DESC
        LIMIT :limit
    """

    conn = _conn(db_conn)
    try:
        result = conn.execute(text(sql), params)
        rows = [dict(row._mapping) for row in result]
    finally:
        if db_conn is None:
            conn.close()
    return rows


def get_normalization_cache(db_conn=None) -> dict:
    """Returns all rows from normalization_cache as {nutrient_key: {min, max}}."""
    sql = "SELECT nutrient_key, min_value, max_value FROM normalization_cache"
    conn = _conn(db_conn)
    try:
        result = conn.execute(text(sql))
        cache = {}
        for row in result:
            cache[row.nutrient_key] = {
                "min": float(row.min_value),
                "max": float(row.max_value),
            }
    finally:
        if db_conn is None:
            conn.close()
    return cache


def log_session(session_data: dict, db_conn=None) -> int:
    """INSERT into recommendation_sessions, return new row ID."""
    sql = """
        INSERT INTO recommendation_sessions
            (session_token, user_id, detected_emotion, emotion_confidence,
             emotion_valence, emotion_arousal, meal_type_filter,
             recommendations, user_selected_id)
        VALUES
            (:session_token, :user_id, :detected_emotion, :emotion_confidence,
             :emotion_valence, :emotion_arousal, :meal_type_filter,
             :recommendations, :user_selected_id)
    """
    params = {
        "session_token":     session_data.get("session_token", ""),
        "user_id":           session_data.get("user_id"),
        "detected_emotion":  session_data.get("detected_emotion", ""),
        "emotion_confidence": session_data.get("emotion_confidence"),
        "emotion_valence":   session_data.get("emotion_valence"),
        "emotion_arousal":   session_data.get("emotion_arousal"),
        "meal_type_filter":  session_data.get("meal_type_filter"),
        "recommendations":   json.dumps(session_data.get("recommendations", [])),
        "user_selected_id":  session_data.get("user_selected_id"),
    }
    conn = _conn(db_conn)
    try:
        result = conn.execute(text(sql), params)
        conn.commit()
        return result.lastrowid
    finally:
        if db_conn is None:
            conn.close()


def log_selection(session_id: int, food_id: int, db_conn=None) -> None:
    """Update recommendation_session row with user's food selection."""
    sql = """
        UPDATE recommendation_sessions
        SET user_selected_id = :food_id
        WHERE id = :session_id
    """
    conn = _conn(db_conn)
    try:
        conn.execute(text(sql), {"food_id": food_id, "session_id": session_id})
        conn.commit()
    finally:
        if db_conn is None:
            conn.close()


def get_food_detail(food_id: int, db_conn=None) -> Optional[dict]:
    """Full details for a single food including all nutrients and ingredients."""
    sql = """
        SELECT f.*, n.*,
               GROUP_CONCAT(fi.ingredient_name SEPARATOR '||') AS ingredients_list
        FROM foods f
        JOIN food_nutrients n ON f.id = n.food_id
        LEFT JOIN food_ingredients fi ON f.id = fi.meal_id
        WHERE f.id = :food_id
        GROUP BY f.id
    """
    conn = _conn(db_conn)
    try:
        result = conn.execute(text(sql), {"food_id": food_id})
        row = result.fetchone()
        if row is None:
            return None
        d = dict(row._mapping)
        raw = d.pop("ingredients_list", None)
        d["ingredients"] = raw.split("||") if raw else []
        return d
    finally:
        if db_conn is None:
            conn.close()


def upsert_user(session_token: str, profile_data: dict, db_conn=None) -> int:
    """Insert or update user record, return user ID."""
    sql_insert = """
        INSERT INTO users (session_token, age, sex, height_cm, weight_kg,
                           bmi, bmi_category, bmr_kcal, tdee_kcal,
                           meal_kcal_target, dietary_restrictions)
        VALUES (:session_token, :age, :sex, :height_cm, :weight_kg,
                :bmi, :bmi_category, :bmr_kcal, :tdee_kcal,
                :meal_kcal_target, :dietary_restrictions)
        ON DUPLICATE KEY UPDATE
            age = VALUES(age), sex = VALUES(sex),
            height_cm = VALUES(height_cm), weight_kg = VALUES(weight_kg),
            bmi = VALUES(bmi), bmi_category = VALUES(bmi_category),
            bmr_kcal = VALUES(bmr_kcal), tdee_kcal = VALUES(tdee_kcal),
            meal_kcal_target = VALUES(meal_kcal_target),
            dietary_restrictions = VALUES(dietary_restrictions),
            updated_at = CURRENT_TIMESTAMP
    """
    params = {
        "session_token":       session_token,
        "age":                 profile_data.get("age"),
        "sex":                 profile_data.get("sex"),
        "height_cm":           profile_data.get("height_cm"),
        "weight_kg":           profile_data.get("weight_kg"),
        "bmi":                 profile_data.get("bmi"),
        "bmi_category":        profile_data.get("bmi_category"),
        "bmr_kcal":            profile_data.get("bmr_kcal"),
        "tdee_kcal":           profile_data.get("tdee_kcal"),
        "meal_kcal_target":    profile_data.get("meal_kcal_target"),
        "dietary_restrictions": json.dumps(profile_data.get("dietary_restrictions", [])),
    }
    conn = _conn(db_conn)
    try:
        result = conn.execute(text(sql_insert), params)
        conn.commit()
        return result.lastrowid or _get_user_id(session_token, conn)
    finally:
        if db_conn is None:
            conn.close()


def _get_user_id(session_token: str, conn) -> Optional[int]:
    result = conn.execute(
        text("SELECT id FROM users WHERE session_token = :t"),
        {"t": session_token}
    )
    row = result.fetchone()
    return row[0] if row else None


def log_restaurant_impression(
    session_id: int,
    food_id: Optional[int],
    restaurant: dict,
    db_conn=None,
) -> int:
    """INSERT into restaurant_impressions. Returns new row id."""
    sql = text("""
        INSERT INTO restaurant_impressions
            (session_id, food_id, place_id, restaurant_name, restaurant_address,
             distance_m, rating, price_level, is_open, r_score, data_source)
        VALUES
            (:session_id, :food_id, :place_id, :name, :address,
             :distance_m, :rating, :price_level, :is_open, :r_score, :source)
    """)
    params = {
        "session_id":  session_id,
        "food_id":     food_id,
        "place_id":    restaurant.get("place_id", ""),
        "name":        restaurant.get("name", "")[:255],
        "address":     (restaurant.get("address") or "")[:500],
        "distance_m":  restaurant.get("distance_m"),
        "rating":      restaurant.get("rating"),
        "price_level": restaurant.get("price_level"),
        "is_open":     restaurant.get("is_open"),
        "r_score":     restaurant.get("r_score"),
        "source":      restaurant.get("source", "google_places"),
    }
    conn = _conn(db_conn)
    try:
        result = conn.execute(sql, params)
        conn.commit()
        return result.lastrowid
    finally:
        if db_conn is None:
            conn.close()


def get_corpus_stats(db_conn=None) -> dict:
    """Return corpus size stats per source and meal_type."""
    sql = """
        SELECT source_dataset, meal_type, COUNT(*) AS n
        FROM foods
        GROUP BY source_dataset, meal_type
        ORDER BY source_dataset, meal_type
    """
    conn = _conn(db_conn)
    try:
        result = conn.execute(text(sql))
        return [dict(row._mapping) for row in result]
    finally:
        if db_conn is None:
            conn.close()
