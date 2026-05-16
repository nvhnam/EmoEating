"""Strip marketing qualifiers from food names to produce clean API search terms."""
from __future__ import annotations
import re

_MARKETING_PATTERNS = [
    r"\bcertified\b", r"\borganic\b", r"\bnatural(?:ly)?\b", r"\ball[- ]natural\b",
    r"\bpremium\b", r"\bgourmet\b", r"\bartisan(?:al)?\b", r"\bhomestyle\b",
    r"\bclassic\b", r"\bauthentic\b", r"\bgluten[- ]free\b", r"\bnon[- ]gmo\b",
    r"\bfresh\b", r"\bextra\b", r"\bsuper\b", r"\bbest\b", r"\bfinest\b",
    r"\blow[- ]fat\b", r"\bfat[- ]free\b", r"\bsugar[- ]free\b",
    r"\bno sugar added\b", r"\bdeluxe\b", r"\bspecial\b",
    r"\bfamily size\b", r"\bvalue pack\b", r"\bwhole grain\b",
    r"\bwild[- ]caught\b", r"\bgrass[- ]fed\b", r"\bfree[- ]range\b",
    r"\braw\b", r"\binstant\b", r"\bhomemade\b", r"\btraditional\b",
]
_MARKETING_RE = re.compile("|".join(_MARKETING_PATTERNS), re.IGNORECASE)
_POSSESSIVE_PREFIX = re.compile(r"^[\w&.\- ]+?'s\s+", re.IGNORECASE)
_RECIPE_NOISE = re.compile(
    r"\b(recipe|recipes|mix|brand|inc|llc|co\b|company|style|from scratch|easy)\b",
    re.IGNORECASE,
)
_PAREN = re.compile(r"\([^)]*\)")
_QUANTITY = re.compile(
    r"\b\d+(\.\d+)?\s?(oz|g|kg|ml|l|lb|lbs|ct|count|pack|piece|pieces)\b",
    re.IGNORECASE,
)
_PUNCT = re.compile(r"[^a-z0-9&\s]")
_SPACES = re.compile(r"\s+")

_STOP = frozenset({"with", "and", "the", "of", "in", "a", "an", "for", "to", "on", "at"})


def normalize_food_name(raw_name: str) -> dict:
    """Return {'core': str, 'tokens': list[str], 'is_branded': bool}.

    Strips marketing qualifiers, brand possessives, recipe noise, and
    parentheticals so the core food name can be used as an API search term.

    Examples:
        "Certified Organic Chia Seeds"   → core="chia seeds"
        "Bon Appetit's Best Bran Muffins Recipe" → core="bran muffins"
        "Pho Bo"                         → core="pho bo"  (passes through unchanged)
    """
    if not raw_name:
        return {"core": "", "tokens": [], "is_branded": False}

    s = raw_name.strip()
    s = _POSSESSIVE_PREFIX.sub("", s)
    s = _MARKETING_RE.sub(" ", s)
    s = _RECIPE_NOISE.sub(" ", s)
    s = _PAREN.sub(" ", s)
    s = _QUANTITY.sub(" ", s)
    s = _PUNCT.sub(" ", s.lower())
    s = _SPACES.sub(" ", s).strip()

    tokens = [t for t in s.split() if t not in _STOP and len(t) > 1]
    core = " ".join(tokens[:4]) if tokens else raw_name.lower().strip()

    is_branded = core.lower() != raw_name.lower().strip()
    return {"core": core, "tokens": tokens, "is_branded": is_branded}
