"""ETL configuration: file paths and dataset names."""

from __future__ import annotations

import os
from pathlib import Path

BASE_DIR    = Path(__file__).parent.parent
DATA_RAW    = BASE_DIR / "data" / "raw"
DATA_PROC   = BASE_DIR / "data" / "processed"
DATA_SQL    = BASE_DIR / "data" / "sql"

# Source dataset filenames (after Kaggle download + unzip)
USDA_FILE          = DATA_RAW / "nutrition.csv"
FOODCOM_RECIPES    = DATA_RAW / "RAW_recipes.csv"
FOODCOM_INTER      = DATA_RAW / "RAW_interactions.csv"
OPENFOODFACTS_FILE = DATA_RAW / "en.openfoodfacts.org.products.tsv"
EPICURIOUS_FILE    = DATA_RAW / "epi_r.csv"
INDIAN_FILE        = DATA_RAW / "indian_food.csv"
VIETNAMESE_FILE    = DATA_RAW / "vietnamese_food.csv"

# DB credentials (resolved from environment)
import sys
sys.path.insert(0, str(BASE_DIR / "app"))

from config import DB_HOST, DB_PORT, DB_NAME, DB_USER, DB_PASS
from sqlalchemy.engine import URL as _URL

DB_URL = _URL.create(
    drivername="mysql+pymysql",
    username=DB_USER,
    password=DB_PASS,
    host=DB_HOST,
    port=DB_PORT,
    database=DB_NAME,
    query={"charset": "utf8mb4"},
)

# Separate schema for Vietnamese food data
VN_DB_NAME = os.getenv("MOODMEAL_VN_DB_NAME", "moodmeal_vn")

VN_DB_URL = _URL.create(
    drivername="mysql+pymysql",
    username=DB_USER,
    password=DB_PASS,
    host=DB_HOST,
    port=DB_PORT,
    database=VN_DB_NAME,
    query={"charset": "utf8mb4"},
)
