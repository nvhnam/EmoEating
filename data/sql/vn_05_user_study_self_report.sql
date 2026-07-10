-- Migration: add self-reported V-A coordinates to recommendation_sessions
-- Vietnamese database (moodmeal_vn) counterpart to 05_user_study_self_report.sql

USE moodmeal_vn;

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

CREATE INDEX IF NOT EXISTS idx_rs_self_zone
    ON recommendation_sessions (self_reported_zone);
