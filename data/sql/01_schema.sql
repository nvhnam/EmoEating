-- ============================================================
-- MoodMeal Research Database Schema
-- Engine: MySQL 8.0+  Charset: utf8mb4
-- ============================================================

CREATE DATABASE IF NOT EXISTS moodmeal
  DEFAULT CHARACTER SET utf8mb4
  DEFAULT COLLATE utf8mb4_unicode_ci;

USE moodmeal;

-- ------------------------------------------------------------
-- TABLE: food_categories
-- ------------------------------------------------------------
CREATE TABLE IF NOT EXISTS food_categories (
    id          TINYINT UNSIGNED AUTO_INCREMENT PRIMARY KEY,
    name        VARCHAR(60) NOT NULL UNIQUE,
    parent_id   TINYINT UNSIGNED NULL,
    FOREIGN KEY (parent_id) REFERENCES food_categories(id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- ------------------------------------------------------------
-- TABLE: foods
-- ------------------------------------------------------------
CREATE TABLE IF NOT EXISTS foods (
    id                  INT UNSIGNED AUTO_INCREMENT PRIMARY KEY,
    name                VARCHAR(255) NOT NULL,
    category_id         TINYINT UNSIGNED NOT NULL,
    meal_type           ENUM('ingredient','complete_meal','snack','beverage') NOT NULL DEFAULT 'complete_meal',
    cuisine             VARCHAR(80) NULL,
    source_dataset      VARCHAR(50) NOT NULL,
    source_id           VARCHAR(100) NULL,
    prep_time_min       SMALLINT UNSIGNED NULL,
    cook_time_min       SMALLINT UNSIGNED NULL,
    servings            TINYINT UNSIGNED NULL DEFAULT 1,
    serving_size_g      SMALLINT UNSIGNED NULL,
    description         TEXT NULL,
    image_url           VARCHAR(500) NULL,
    is_vegetarian       BOOLEAN NOT NULL DEFAULT FALSE,
    is_vegan            BOOLEAN NOT NULL DEFAULT FALSE,
    is_gluten_free      BOOLEAN NOT NULL DEFAULT FALSE,
    is_dairy_free       BOOLEAN NOT NULL DEFAULT FALSE,
    rating              DECIMAL(3,2) NULL,
    rating_count        MEDIUMINT UNSIGNED NULL DEFAULT 0,
    created_at          TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (category_id) REFERENCES food_categories(id),
    INDEX idx_meal_type (meal_type),
    INDEX idx_cuisine (cuisine),
    INDEX idx_source (source_dataset),
    FULLTEXT INDEX ft_name (name)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- ------------------------------------------------------------
-- TABLE: food_nutrients
-- ------------------------------------------------------------
CREATE TABLE IF NOT EXISTS food_nutrients (
    food_id             INT UNSIGNED PRIMARY KEY,
    calories_kcal       DECIMAL(8,2) NULL,
    protein_g           DECIMAL(8,3) NULL,
    carbohydrate_g      DECIMAL(8,3) NULL,
    complex_carbs_g     DECIMAL(8,3) NULL,
    fiber_g             DECIMAL(8,3) NULL,
    sugar_g             DECIMAL(8,3) NULL,
    fat_g               DECIMAL(8,3) NULL,
    saturated_fat_g     DECIMAL(8,3) NULL,
    tryptophan_mg       DECIMAL(8,3) NULL,
    omega3_mg           DECIMAL(8,3) NULL,
    magnesium_mg        DECIMAL(8,3) NULL,
    iron_mg             DECIMAL(8,3) NULL,
    vitamin_b12_mcg     DECIMAL(8,3) NULL,
    folate_mcg          DECIMAL(8,3) NULL,
    vitamin_c_mg        DECIMAL(8,3) NULL,
    vitamin_e_mg        DECIMAL(8,3) NULL,
    vitamin_a_mcg       DECIMAL(8,3) NULL,
    calcium_mg          DECIMAL(8,3) NULL,
    zinc_mg             DECIMAL(8,3) NULL,
    potassium_mg        DECIMAL(8,3) NULL,
    sodium_mg           DECIMAL(8,3) NULL,
    cholesterol_mg      DECIMAL(8,3) NULL,
    data_completeness   TINYINT UNSIGNED NOT NULL DEFAULT 0,
    FOREIGN KEY (food_id) REFERENCES foods(id) ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- ------------------------------------------------------------
-- TABLE: tags
-- ------------------------------------------------------------
CREATE TABLE IF NOT EXISTS tags (
    id      SMALLINT UNSIGNED AUTO_INCREMENT PRIMARY KEY,
    tag     VARCHAR(80) NOT NULL UNIQUE,
    INDEX idx_tag (tag)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- ------------------------------------------------------------
-- TABLE: food_tags
-- ------------------------------------------------------------
CREATE TABLE IF NOT EXISTS food_tags (
    food_id INT UNSIGNED NOT NULL,
    tag_id  SMALLINT UNSIGNED NOT NULL,
    PRIMARY KEY (food_id, tag_id),
    FOREIGN KEY (food_id) REFERENCES foods(id) ON DELETE CASCADE,
    FOREIGN KEY (tag_id)  REFERENCES tags(id)  ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- ------------------------------------------------------------
-- TABLE: food_ingredients
-- ------------------------------------------------------------
CREATE TABLE IF NOT EXISTS food_ingredients (
    id              INT UNSIGNED AUTO_INCREMENT PRIMARY KEY,
    meal_id         INT UNSIGNED NOT NULL,
    ingredient_name VARCHAR(200) NOT NULL,
    ingredient_id   INT UNSIGNED NULL,
    quantity_g      DECIMAL(8,2) NULL,
    FOREIGN KEY (meal_id)        REFERENCES foods(id) ON DELETE CASCADE,
    FOREIGN KEY (ingredient_id)  REFERENCES foods(id),
    INDEX idx_meal (meal_id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- ------------------------------------------------------------
-- TABLE: normalization_cache
-- ------------------------------------------------------------
CREATE TABLE IF NOT EXISTS normalization_cache (
    nutrient_key    VARCHAR(50) PRIMARY KEY,
    min_value       DECIMAL(12,4) NOT NULL,
    max_value       DECIMAL(12,4) NOT NULL,
    updated_at      TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- ------------------------------------------------------------
-- TABLE: users
-- ------------------------------------------------------------
CREATE TABLE IF NOT EXISTS users (
    id              INT UNSIGNED AUTO_INCREMENT PRIMARY KEY,
    session_token   VARCHAR(64) NOT NULL UNIQUE,
    age             TINYINT UNSIGNED NULL,
    sex             ENUM('male','female','other','prefer_not_to_say') NULL,
    height_cm       SMALLINT UNSIGNED NULL,
    weight_kg       DECIMAL(5,1) NULL,
    bmi             DECIMAL(4,1) NULL,
    bmi_category    ENUM('underweight','normal','overweight','obese') NULL,
    bmr_kcal        DECIMAL(7,1) NULL,
    tdee_kcal       DECIMAL(7,1) NULL,
    meal_kcal_target DECIMAL(6,1) NULL,
    dietary_restrictions JSON NULL,
    created_at      TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at      TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- ------------------------------------------------------------
-- TABLE: recommendation_sessions
-- ------------------------------------------------------------
CREATE TABLE IF NOT EXISTS recommendation_sessions (
    id                  BIGINT UNSIGNED AUTO_INCREMENT PRIMARY KEY,
    user_id             INT UNSIGNED NULL,
    session_token       VARCHAR(64) NOT NULL,
    detected_emotion    VARCHAR(30) NOT NULL,
    emotion_confidence  DECIMAL(4,3) NULL,
    emotion_valence     DECIMAL(4,3) NULL,
    emotion_arousal     DECIMAL(4,3) NULL,
    meal_type_filter    VARCHAR(20) NULL,
    recommendations     JSON NOT NULL,
    user_selected_id    INT UNSIGNED NULL,
    satisfaction_rating TINYINT UNSIGNED NULL,
    created_at          TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (user_id)         REFERENCES users(id),
    FOREIGN KEY (user_selected_id) REFERENCES foods(id),
    INDEX idx_emotion (detected_emotion),
    INDEX idx_session (session_token),
    INDEX idx_created (created_at)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- ------------------------------------------------------------
-- VIEW: meals_with_nutrients
-- ------------------------------------------------------------
CREATE OR REPLACE VIEW meals_with_nutrients AS
SELECT
    f.id,
    f.name,
    f.description,
    f.image_url,
    fc.name          AS category,
    f.meal_type,
    f.cuisine,
    f.is_vegetarian,
    f.is_vegan,
    f.is_gluten_free,
    f.is_dairy_free,
    f.rating,
    f.prep_time_min,
    f.cook_time_min,
    f.serving_size_g,
    n.calories_kcal,
    n.protein_g,
    n.carbohydrate_g,
    n.complex_carbs_g,
    n.fiber_g,
    n.sugar_g,
    n.tryptophan_mg,
    n.omega3_mg,
    n.magnesium_mg,
    n.iron_mg,
    n.vitamin_b12_mcg,
    n.folate_mcg,
    n.vitamin_c_mg,
    n.vitamin_e_mg,
    n.data_completeness
FROM foods f
JOIN food_categories fc ON f.category_id = fc.id
JOIN food_nutrients  n  ON f.id = n.food_id
WHERE f.meal_type IN ('complete_meal','snack','beverage');

-- ------------------------------------------------------------
-- TABLE: restaurant_impressions
-- ------------------------------------------------------------
CREATE TABLE IF NOT EXISTS restaurant_impressions (
    id                 BIGINT UNSIGNED AUTO_INCREMENT PRIMARY KEY,
    session_id         BIGINT UNSIGNED NOT NULL,
    food_id            INT UNSIGNED NULL,
    place_id           VARCHAR(255) NOT NULL,
    restaurant_name    VARCHAR(255) NOT NULL,
    restaurant_address VARCHAR(500) NULL,
    distance_m         FLOAT NULL,
    rating             DECIMAL(3,2) NULL,
    price_level        TINYINT UNSIGNED NULL,
    is_open            BOOLEAN NULL,
    r_score            DECIMAL(6,5) NULL,
    data_source        ENUM('google_places','foursquare','here','osm') NOT NULL DEFAULT 'google_places',
    -- maps_clicked is reserved for future click-tracking instrumentation.
    -- It is NOT set by the current implementation (the "View on Maps →" link
    -- is a plain <a> tag with no server-side callback). Log rows are inserted
    -- with maps_clicked=FALSE. A future version may use st.experimental_get_query_params
    -- or a redirect endpoint to flip this flag. Do not attempt to set it to TRUE now.
    maps_clicked       BOOLEAN NOT NULL DEFAULT FALSE,
    shown_at           TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (session_id) REFERENCES recommendation_sessions(id) ON DELETE CASCADE,
    FOREIGN KEY (food_id)    REFERENCES foods(id) ON DELETE SET NULL,
    INDEX idx_ri_session  (session_id),
    INDEX idx_ri_food     (food_id),
    INDEX idx_ri_shown_at (shown_at)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;
