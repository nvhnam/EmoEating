"""
Classifies meal type from tags, category strings, or recipe names.
Returns (category_id, meal_type) tuple.
"""

from __future__ import annotations

import re

MEAL_TAG_MAP = {
    "breakfast": (1, "complete_meal"),
    "brunch":    (1, "complete_meal"),
    "lunch":     (2, "complete_meal"),
    "dinner":    (3, "complete_meal"),
    "main-dish": (3, "complete_meal"),
    "main dish": (3, "complete_meal"),
    "main_dish": (3, "complete_meal"),
    "main course": (3, "complete_meal"),
    "snack":     (4, "snack"),
    "appetizer": (4, "snack"),
    "starter":   (4, "snack"),
    "dessert":   (5, "complete_meal"),
    "sweet":     (5, "complete_meal"),
    "beverages": (6, "beverage"),
    "beverage":  (6, "beverage"),
    "drink":     (6, "beverage"),
    "smoothie":  (6, "beverage"),
    "side-dishes": (7, "complete_meal"),
    "side dish": (7, "complete_meal"),
    "side_dish": (7, "complete_meal"),
    "soups-stews": (9, "complete_meal"),
    "soup":      (9, "complete_meal"),
    "stew":      (9, "complete_meal"),
    "salads":    (10, "complete_meal"),
    "salad":     (10, "complete_meal"),
}

DEFAULT = (3, "complete_meal")  # dinner / complete_meal


def classify_from_tags(tags_list: list[str]) -> tuple[int, str]:
    """Given a list of tag strings, return (category_id, meal_type)."""
    for tag in tags_list:
        t = tag.lower().strip()
        if t in MEAL_TAG_MAP:
            return MEAL_TAG_MAP[t]
    return DEFAULT


def classify_from_text(text: str) -> tuple[int, str]:
    """Classify from a free-text category or title string."""
    t = text.lower()
    for key, val in MEAL_TAG_MAP.items():
        if key in t:
            return val
    return DEFAULT


def indian_course_to_category(course: str) -> tuple[int, str]:
    """Map Indian food dataset 'course' field to (category_id, meal_type)."""
    mapping = {
        "main course":  (3, "complete_meal"),
        "starter":      (4, "snack"),
        "dessert":      (5, "complete_meal"),
        "snack":        (4, "snack"),
        "breakfast":    (1, "complete_meal"),
        "side dish":    (7, "complete_meal"),
        "beverage":     (6, "beverage"),
    }
    return mapping.get(str(course).lower().strip(), DEFAULT)
