import httpx
from emoeating.external.images import (
    ImageProvider, NullImageProvider, GoogleImageProvider,
)


def test_null_provider_is_disabled_and_empty():
    p: ImageProvider = NullImageProvider()
    assert p.enabled is False
    assert p.images("pizza") == []


def _mock_client(handler):
    return httpx.Client(transport=httpx.MockTransport(handler))


def test_google_provider_returns_capped_links():
    captured = {}

    def handler(request: httpx.Request) -> httpx.Response:
        captured["params"] = dict(request.url.params)
        return httpx.Response(200, json={"items": [
            {"link": "http://img/1.jpg"},
            {"link": "http://img/2.jpg"},
            {"link": "http://img/3.jpg"},
            {"link": "http://img/4.jpg"},
        ]})

    p = GoogleImageProvider("img-key", "cx-id", client=_mock_client(handler))
    urls = p.images("sushi", limit=3)
    assert p.enabled is True
    assert urls == ["http://img/1.jpg", "http://img/2.jpg", "http://img/3.jpg"]
    assert captured["params"]["q"] == "sushi"
    assert captured["params"]["key"] == "img-key"
    assert captured["params"]["cx"] == "cx-id"
    assert captured["params"]["searchType"] == "image"


def test_google_provider_degrades_on_http_error():
    def handler(request):
        return httpx.Response(500, json={"error": "boom"})

    p = GoogleImageProvider("k", "c", client=_mock_client(handler))
    assert p.images("ramen") == []


def test_google_provider_degrades_on_network_error():
    def handler(request):
        raise httpx.ConnectError("refused")
    p = GoogleImageProvider("k", "c", client=_mock_client(handler))
    assert p.images("ramen") == []


def test_google_provider_degrades_on_malformed_json():
    def handler(request):
        return httpx.Response(200, content=b"not-json")
    p = GoogleImageProvider("k", "c", client=_mock_client(handler))
    assert p.images("ramen") == []


def test_google_provider_degrades_on_null_json():
    def handler(request):
        return httpx.Response(200, content=b"null")
    p = GoogleImageProvider("k", "c", client=_mock_client(handler))
    assert p.images("ramen") == []


def test_google_provider_degrades_when_items_is_not_a_list():
    """A 200 response with items as a non-list (dict or string) must return []."""
    def handler(request):
        return httpx.Response(200, json={"items": {"unexpected": "dict"}})
    p = GoogleImageProvider("k", "c", client=_mock_client(handler))
    assert p.images("ramen") == []

    def handler_str(request):
        return httpx.Response(200, json={"items": "not-a-list"})
    p2 = GoogleImageProvider("k", "c", client=_mock_client(handler_str))
    assert p2.images("ramen") == []


def test_image_provider_protocol_is_runtime_checkable():
    assert isinstance(NullImageProvider(), ImageProvider)
