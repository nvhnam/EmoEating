from fastapi.testclient import TestClient

from api import routes
from api.main import create_app
from emoeating.data.schema import Food
from tests.conftest import TEST_SETTINGS, FakeStore


def test_foods_returns_catalog_shape(client):
    r = client.get("/api/foods")
    assert r.status_code == 200
    foods = r.json()["foods"]
    assert [f["id"] for f in foods] == ["salmon", "candy"]
    assert set(foods[0]) == {"id", "name", "source", "calories", "image_hint"}


def test_foods_caps_at_200():
    many = [
        Food(id=f"f{i:03d}", name=f"Food {i}", source="test",
             calories=100.0, nutrients={}, image_hint=None)
        for i in range(250)
    ]
    app = create_app(TEST_SETTINGS)
    app.dependency_overrides[routes.get_store] = lambda: FakeStore(many)
    c = TestClient(app)
    assert len(c.get("/api/foods").json()["foods"]) == 200


def test_foods_503_when_store_missing():
    app = create_app(TEST_SETTINGS)
    app.dependency_overrides[routes.get_store] = lambda: None
    c = TestClient(app)
    assert c.get("/api/foods").status_code == 503
