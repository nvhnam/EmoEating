from fastapi.testclient import TestClient

from api import routes
from emoeating.external.restaurants import Place


def test_restaurants_degraded_with_null_provider(client):
    r = client.get("/api/restaurants", params={"food": "pho", "lat": 10.77, "lng": 106.69})
    assert r.status_code == 200
    assert r.json() == {"places": [], "disabled": True}


def test_restaurants_returns_places_when_enabled(app):
    class FakeRestaurants:
        enabled = True

        def nearby(self, food, lat, lng, radius_m=11000):
            return [Place(name="Corner Pho", lat=10.77, lng=106.69,
                          distance_m=120.0, address="1 Near St")]

    app.dependency_overrides[routes.get_restaurant_provider] = lambda: FakeRestaurants()
    client = TestClient(app)
    r = client.get("/api/restaurants", params={"food": "pho", "lat": 10.77, "lng": 106.69})
    body = r.json()
    assert body["disabled"] is False
    assert body["places"][0]["name"] == "Corner Pho"
    assert body["places"][0]["distance_m"] == 120.0


def test_restaurants_requires_lat_lng(client):
    assert client.get("/api/restaurants", params={"food": "pho"}).status_code == 422
