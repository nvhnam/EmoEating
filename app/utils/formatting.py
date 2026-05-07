"""Number formatting and portion size display helpers."""

from __future__ import annotations

def fmt_kcal(kcal) -> str:
    if kcal is None:
        return "â€”"
    return f"{int(round(kcal))} kcal"


def fmt_g(value, decimals: int = 1) -> str:
    if value is None:
        return "â€”"
    return f"{round(float(value), decimals)}g"


def fmt_mg(value, decimals: int = 1) -> str:
    if value is None:
        return "â€”"
    return f"{round(float(value), decimals)}mg"


def fmt_time(minutes) -> str:
    if minutes is None:
        return "â€”"
    m = int(minutes)
    if m < 60:
        return f"{m} min"
    h = m // 60
    rem = m % 60
    return f"{h}h {rem}m" if rem else f"{h}h"


def fmt_score(score: float) -> str:
    return f"{score:.3f}"


def fmt_bmi(bmi: float) -> str:
    return f"{bmi:.1f}"


def portion_size_label(serving_size_g) -> str:
    if serving_size_g is None:
        return ""
    return f"~{int(serving_size_g)}g serving"


def kcal_match_pct(food_kcal, target_kcal) -> float:
    """Return 0â€“1 fraction of how close food_kcal is to target_kcal."""
    if food_kcal is None or target_kcal is None or target_kcal <= 0:
        return 0.0
    ratio = float(food_kcal) / float(target_kcal)
    return min(ratio, 1.0 / ratio)


BMI_CATEGORY_COLORS = {
    "underweight": "#85B7EB",
    "normal":      "#2d9e5a",
    "overweight":  "#e6a817",
    "obese":       "#E24B4A",
}


def bmi_category_color(category: str) -> str:
    return BMI_CATEGORY_COLORS.get(category, "#888780")
