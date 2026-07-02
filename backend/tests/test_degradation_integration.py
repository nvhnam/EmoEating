# backend/tests/test_degradation_integration.py


def test_full_flow_degrades_gracefully_without_google_keys(client):
    # 1. recommend returns ranked meals despite no external keys (zone comes from
    #    the live /ws/emotion session in production; a literal stands in here)
    rec = client.post("/api/recommend", json={"zone": "NEG_DEACTIVE"})
    assert rec.status_code == 200
    assert len(rec.json()["meals"]) >= 1

    # 2. images disabled + empty
    img = client.get("/api/images", params={"food": "salmon"})
    assert img.status_code == 200
    assert img.json() == {"images": [], "disabled": True}

    # 3. restaurants disabled + empty
    rest = client.get("/api/restaurants",
                      params={"food": "salmon", "lat": 10.77, "lng": 106.69})
    assert rest.status_code == 200
    assert rest.json() == {"places": [], "disabled": True}


def test_no_external_calls_are_made(monkeypatch):
    # Hard guard: a real httpx request during the degraded flow would raise.
    # NOTE: We patch httpx.HTTPTransport / AsyncHTTPTransport (the real network
    # transport layer) instead of httpx.Client.send.  Patching Client.send would
    # break TestClient itself because in httpx >= 0.20 TestClient's own
    # ASGITransport is dispatched through Client.send.  The real transports are
    # only invoked for genuine outbound sockets, so ASGITransport still works.
    import httpx

    def _boom(*a, **k):
        raise AssertionError("live network call attempted in tests")

    monkeypatch.setattr(httpx.HTTPTransport, "handle_request", _boom)
    monkeypatch.setattr(httpx.AsyncHTTPTransport, "handle_async_request", _boom)
    # importing the client fixture body inline keeps the guard local to this test
    from fastapi.testclient import TestClient
    from api.main import create_app
    from api import routes
    from tests.conftest import TEST_SETTINGS, FakeStore, SAMPLE_FOODS

    app = create_app(TEST_SETTINGS)
    app.dependency_overrides[routes.get_store] = lambda: FakeStore(SAMPLE_FOODS)
    c = TestClient(app)
    assert c.get("/api/images", params={"food": "x"}).json()["disabled"] is True
    assert c.get("/api/restaurants",
                 params={"food": "x", "lat": 0, "lng": 0}).json()["disabled"] is True
