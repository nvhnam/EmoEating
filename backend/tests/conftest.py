import pytest
from fastapi.testclient import TestClient

from emoeating.config import Settings
from emoeating.data.schema import Food

from api.main import create_app
from api import routes


@pytest.fixture(autouse=True)
def _no_dotenv(monkeypatch):
    """Keep tests hermetic: never load a developer's local backend/.env.

    load_settings() calls load_dotenv(); pytest runs from backend/, so without this
    a real .env would leak (e.g. EMOEATING_VOICE_PROVIDER) and break default-asserting
    tests. Patch both the already-bound reference in config and the dotenv source, so
    tests that importlib.reload(config) stay neutralized too.
    """
    def _noop(*args, **kwargs):
        return False

    monkeypatch.setattr("dotenv.load_dotenv", _noop)
    import emoeating.config as _cfg
    monkeypatch.setattr(_cfg, "load_dotenv", _noop, raising=False)

# settings with NO keys -> Null providers -> degraded mode by default
TEST_SETTINGS = Settings(
    google_image_api_key=None,
    google_image_cx=None,
    google_places_api_key=None,
    emo_model_path=None,
    store_path=None,
    cors_origins=("http://localhost:5173",),
)

SAMPLE_FOODS = [
    Food(id="salmon", name="Grilled Salmon", source="usda", calories=400.0,
         nutrients={"protein_g": 40, "fat_g": 20, "omega3_g": 2.5,
                    "vit_d_ug": 15, "vit_b12_ug": 3, "folate_ug": 140},
         image_hint="salmon fillet"),
    Food(id="candy", name="Gummy Candy", source="off", calories=350.0,
         nutrients={"carb_g": 80}, image_hint=None),
]


class FakeStore:
    """In-memory FoodStore stand-in (subsystem 2 interface)."""
    def __init__(self, foods):
        self._foods = list(foods)

    def candidates(self, limit=200):
        return self._foods[:limit]

    def all_foods(self):
        return list(self._foods)


@pytest.fixture
def app():
    application = create_app(TEST_SETTINGS)
    application.dependency_overrides[routes.get_store] = lambda: FakeStore(SAMPLE_FOODS)
    return application


@pytest.fixture
def client(app):
    return TestClient(app)
