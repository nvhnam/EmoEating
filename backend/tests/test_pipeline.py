# backend/tests/test_pipeline.py
from emoeating.pipeline import recommend, RecommendationResult
from emoeating.data.schema import Food, Zone


def _food(fid, **nutrients):
    return Food(id=fid, name=fid, source="t", calories=None, nutrients=nutrients)


def test_recommend_routes_sad_to_neg_deactive_and_ranks():
    foods = [
        _food("salmon", protein_g=40, fat_g=20, omega3_g=2.5, vit_d_ug=15, vit_b12_ug=3),
        _food("candy", carb_g=80),
    ]
    probs = {"sad": 0.7, "neutral": 0.2, "happy": 0.1}
    result = recommend(probs, foods, profile=None, top_n=10)
    assert isinstance(result, RecommendationResult)
    assert result.zone == Zone.NEG_DEACTIVE
    # the omega-3/B12/D-rich food should outrank plain sugar in this zone
    assert result.recommendations[0].food.id == "salmon"


def test_top_n_truncates():
    foods = [_food(str(i), carb_g=10 * i) for i in range(20)]
    result = recommend({"happy": 1.0}, foods, top_n=5)
    assert len(result.recommendations) == 5
