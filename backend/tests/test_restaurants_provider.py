# backend/tests/test_restaurants_provider.py
import httpx
from emoeating.external.restaurants import (
    Place, NullRestaurantProvider, GooglePlacesProvider,
)


def test_null_provider_is_disabled_and_empty():
    p = NullRestaurantProvider()
    assert p.enabled is False
    assert p.nearby("pho", 10.77, 106.69) == []


def _mock_client(handler):
    return httpx.Client(transport=httpx.MockTransport(handler))


def _places_payload():
    # one ~0 m away, one absurdly far (other hemisphere) -> filtered out
    return {"results": [
        {"name": "Corner Pho", "formatted_address": "1 Near St",
         "geometry": {"location": {"lat": 10.7701, "lng": 106.6901}}},
        {"name": "Far Diner", "formatted_address": "Antipode Ave",
         "geometry": {"location": {"lat": -10.77, "lng": -73.31}}},
    ]}


def test_google_places_filters_to_radius_and_sorts():
    def handler(request):
        return httpx.Response(200, json=_places_payload())

    p = GooglePlacesProvider("places-key", client=_mock_client(handler))
    out = p.nearby("pho", 10.77, 106.69, radius_m=11000)
    assert p.enabled is True
    assert [pl.name for pl in out] == ["Corner Pho"]      # far one dropped
    assert isinstance(out[0], Place)
    assert out[0].distance_m < 200
    assert out[0].address == "1 Near St"


def test_google_places_degrades_on_error():
    def handler(request):
        return httpx.Response(403, json={"error": "no billing"})

    p = GooglePlacesProvider("k", client=_mock_client(handler))
    assert p.nearby("pho", 10.77, 106.69) == []


def test_google_places_degrades_on_network_error():
    def handler(request):
        raise httpx.ConnectError("refused")

    p = GooglePlacesProvider("k", client=_mock_client(handler))
    assert p.nearby("pho", 10.77, 106.69) == []


def test_google_places_degrades_on_malformed_json():
    def handler(request):
        return httpx.Response(200, content=b"not-json")

    p = GooglePlacesProvider("k", client=_mock_client(handler))
    assert p.nearby("pho", 10.77, 106.69) == []


def test_google_places_degrades_on_non_dict_json():
    def handler(request):
        return httpx.Response(200, json=[])

    p = GooglePlacesProvider("k", client=_mock_client(handler))
    assert p.nearby("pho", 10.77, 106.69) == []


def test_google_places_degrades_when_results_is_not_a_list():
    """A 200 response with results as a non-list (dict or string) must return []."""
    def handler(request):
        return httpx.Response(200, json={"results": {"unexpected": "dict"}})
    p = GooglePlacesProvider("k", client=_mock_client(handler))
    assert p.nearby("pho", 10.77, 106.69) == []

    def handler_str(request):
        return httpx.Response(200, json={"results": "not-a-list"})
    p2 = GooglePlacesProvider("k", client=_mock_client(handler_str))
    assert p2.nearby("pho", 10.77, 106.69) == []
