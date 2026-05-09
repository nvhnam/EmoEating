-- Run this against existing moodmeal and moodmeal_vn databases to extend
-- the data_source ENUM so Foursquare and HERE results can be logged correctly.
-- Safe to run multiple times (MySQL MODIFY COLUMN is idempotent here).

ALTER TABLE moodmeal.restaurant_impressions
  MODIFY COLUMN data_source
    ENUM('google_places','foursquare','here','osm') NOT NULL DEFAULT 'google_places';

ALTER TABLE moodmeal_vn.restaurant_impressions
  MODIFY COLUMN data_source
    ENUM('google_places','foursquare','here','osm') NOT NULL DEFAULT 'google_places';
