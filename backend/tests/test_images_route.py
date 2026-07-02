# backend/tests/test_images_route.py
from api import routes


def test_images_degraded_with_null_provider(client):
    r = client.get("/api/images", params={"food": "pizza"})
    assert r.status_code == 200
    assert r.json() == {"images": [], "disabled": True}


def test_images_returns_urls_when_provider_enabled(app):
    from fastapi.testclient import TestClient

    class FakeImages:
        enabled = True

        def images(self, food, limit=3):
            return ["http://img/a.jpg", "http://img/b.jpg"]

    app.dependency_overrides[routes.get_image_provider] = lambda: FakeImages()
    client = TestClient(app)
    r = client.get("/api/images", params={"food": "sushi"})
    assert r.json() == {"images": ["http://img/a.jpg", "http://img/b.jpg"], "disabled": False}


def test_images_requires_food_param(client):
    assert client.get("/api/images").status_code == 422
