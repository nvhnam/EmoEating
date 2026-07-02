from emoeating.affect.zones import assign_zone
from emoeating.data.schema import Zone


def test_pos_active():
    assert assign_zone(0.8, 0.5) == Zone.POS_ACTIVE


def test_neg_active():
    assert assign_zone(-0.7, 0.7) == Zone.NEG_ACTIVE


def test_neg_deactive():
    assert assign_zone(-0.7, -0.5) == Zone.NEG_DEACTIVE


def test_neutral_calm_dead_zone():
    assert assign_zone(0.0, 0.0) == Zone.NEUTRAL_CALM
    # low-arousal positive valence falls through to the calm baseline
    assert assign_zone(0.5, -0.4) == Zone.NEUTRAL_CALM
    # exactly on the threshold is not strictly greater -> not POS_ACTIVE
    assert assign_zone(0.25, 0.25) == Zone.NEUTRAL_CALM


def test_neg_deactive_arousal_at_threshold_boundary():
    # arousal exactly at threshold (0.25) with valence < -threshold
    # This covers the load-bearing <= condition in NEG_DEACTIVE
    assert assign_zone(-0.5, 0.25) == Zone.NEG_DEACTIVE
    # arousal at threshold but valence NOT strictly < -threshold
    # falls through to NEUTRAL_CALM (valence = -0.25 is not < -0.25)
    assert assign_zone(-0.25, 0.25) == Zone.NEUTRAL_CALM
