-- ============================================================
-- LEGACY MIGRATION — DO NOT RUN ON A FRESH INSTALL
-- ============================================================
-- This migration adds self_reported_v, self_reported_a, self_reported_zone
-- to recommendation_sessions for guide.md Phase 7 zone agreement analysis.
--
-- FRESH INSTALL (schema v2+, 01_schema.sql dated 2026-05-24 or later):
--   These columns are already in 01_schema.sql. Do NOT run this file.
--
-- EXISTING DATABASE (schema built before 2026-05-24):
--   Run this once to add Phase 7 columns to an old database:
--   mysql -u root -p moodmeal < data/sql/05_user_study_self_report.sql
--
-- Safe to run multiple times (ADD COLUMN IF NOT EXISTS).

USE moodmeal;

ALTER TABLE recommendation_sessions
    ADD COLUMN IF NOT EXISTS self_reported_v    DECIMAL(5,4) NULL
        COMMENT 'Valence [-1,+1] from affect grid, participant self-report'
        AFTER emotion_arousal,
    ADD COLUMN IF NOT EXISTS self_reported_a    DECIMAL(5,4) NULL
        COMMENT 'Arousal [-1,+1] from affect grid, participant self-report'
        AFTER self_reported_v,
    ADD COLUMN IF NOT EXISTS self_reported_zone VARCHAR(30)  NULL
        COMMENT 'Zone derived from self-reported V-A (ground truth for zone agreement)'
        AFTER self_reported_a;

-- Optional index for zone agreement queries
CREATE INDEX IF NOT EXISTS idx_rs_self_zone
    ON recommendation_sessions (self_reported_zone);
