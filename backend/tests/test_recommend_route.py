def test_recommend_ranks_meals_and_returns_nnv(client):
    r = client.post("/api/recommend", json={"zone": "NEG_DEACTIVE"})
    assert r.status_code == 200
    body = r.json()
    ids = [m["food"]["id"] for m in body["meals"]]
    assert ids[0] == "salmon"                      # omega3/B12/D-rich wins this zone
    meal = body["meals"][0]
    assert 0.0 <= meal["m_macro"] <= 1.0
    assert 0.0 <= meal["m_micro"] <= 1.0
    assert "enms" in meal
    assert isinstance(meal["satisfied_targets"], list)
    assert body["nnv"]["zone"] == "NEG_DEACTIVE"
    assert "omega3_g" in body["nnv"]["priority_micros"]


def test_recommend_accepts_profile(client):
    r = client.post("/api/recommend", json={
        "zone": "POS_ACTIVE",
        "profile": {"age": 30, "sex": "male", "height_cm": 180,
                    "weight_kg": 80, "activity": "moderate"},
    })
    assert r.status_code == 200
    assert r.json()["nnv"]["macro_targets"]["carb_g"] > 0


def test_recommend_rejects_unknown_zone(client):
    r = client.post("/api/recommend", json={"zone": "ECSTATIC"})
    assert r.status_code == 422
