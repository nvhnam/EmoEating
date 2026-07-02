from emoeating import config


def test_enms_weights_sum_to_one():
    assert abs(config.ALPHA + config.BETA + config.GAMMA - 1.0) < 1e-9
    assert config.THETA == 0.25


def test_emotion_va_has_nine_classes_in_range():
    assert len(config.EMOTION_VA) == 9
    for v, a in config.EMOTION_VA.values():
        assert -1.0 <= v <= 1.0 and -1.0 <= a <= 1.0


def test_zone_macro_ratios_sum_to_one():
    for zone, r in config.ZONE_MACRO_RATIOS.items():
        assert set(r) == {"protein", "carb", "fat"}
        assert abs(sum(r.values()) - 1.0) < 1e-9


def test_priority_micros_have_rda_entries():
    for micros in config.ZONE_PRIORITY_MICROS.values():
        for n in micros:
            assert n in config.MICRO_RDA
