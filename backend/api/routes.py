"""HTTP surface: dependency seams + (endpoints added in later tasks)."""
from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel

from emoeating.config import MEAL_ENERGY_FRACTIONS
from emoeating.data.schema import Food, Zone
from emoeating.data.store import FoodStore
from emoeating.external.images import ImageProvider
from emoeating.external.restaurants import RestaurantProvider
from emoeating.nutrition.energy import Profile
from emoeating.nutrition.enms import macro_score, micro_score, rank_foods
from emoeating.nutrition.nnv import NutritionalNeedVector, build_nnv

router = APIRouter()


def get_store(request: Request) -> FoodStore:
    store = request.app.state.store
    if store is None:
        raise HTTPException(status_code=503, detail="food store not configured")
    return store


def get_image_provider(request: Request) -> ImageProvider:
    return request.app.state.image_provider


def get_restaurant_provider(request: Request) -> RestaurantProvider:
    return request.app.state.restaurant_provider


class ImageResponse(BaseModel):
    images: list[str]
    disabled: bool


class PlaceOut(BaseModel):
    name: str
    lat: float
    lng: float
    distance_m: float
    address: str


class RestaurantResponse(BaseModel):
    places: list[PlaceOut]
    disabled: bool


@router.get("/api/images", response_model=ImageResponse)
def images(
    food: str,
    provider: ImageProvider = Depends(get_image_provider),
) -> ImageResponse:
    return ImageResponse(images=provider.images(food, limit=3), disabled=not provider.enabled)


@router.get("/api/restaurants", response_model=RestaurantResponse)
def restaurants(
    food: str,
    lat: float,
    lng: float,
    provider: RestaurantProvider = Depends(get_restaurant_provider),
) -> RestaurantResponse:
    places = provider.nearby(food, lat, lng)
    return RestaurantResponse(
        places=[PlaceOut(name=p.name, lat=p.lat, lng=p.lng,
                         distance_m=p.distance_m, address=p.address) for p in places],
        disabled=not provider.enabled,
    )


class ProfileIn(BaseModel):
    age: int
    sex: str
    height_cm: float
    weight_kg: float
    activity: str


class RecommendRequest(BaseModel):
    zone: str
    profile: ProfileIn | None = None
    meal_type: str | None = None   # breakfast|lunch|dinner|snack; None -> flat 1/3


class FoodOut(BaseModel):
    id: str
    name: str
    source: str
    calories: float | None
    image_hint: str | None = None
    # Per-spec §5 the food payload is {id,name,source,calories,image_hint}; which
    # nutrient targets a meal satisfies is conveyed by MealOut.satisfied_targets,
    # so the full per-food nutrients dict is intentionally not serialized.


class MealOut(BaseModel):
    food: FoodOut
    enms: float
    m_macro: float
    m_micro: float
    satisfied_targets: list[str]


class NNVOut(BaseModel):
    zone: str
    macro_targets: dict[str, float]
    macro_weights: dict[str, float]
    micro_targets: dict[str, float]
    priority_micros: list[str]


class RecommendResponse(BaseModel):
    meals: list[MealOut]
    nnv: NNVOut


def _food_out(food: Food) -> FoodOut:
    return FoodOut(id=food.id, name=food.name, source=food.source,
                   calories=food.calories, image_hint=food.image_hint)


def _satisfied_targets(food: Food, nnv: NutritionalNeedVector) -> list[str]:
    keys: list[str] = []
    for k, t in nnv.macro_targets.items():
        if t > 0 and food.amount(k) >= t:
            keys.append(k)
    for k in nnv.priority_micros:
        if nnv.micro_targets[k] > 0 and food.amount(k) >= nnv.micro_targets[k]:
            keys.append(k)
    return keys


def _nnv_out(nnv: NutritionalNeedVector) -> NNVOut:
    return NNVOut(zone=nnv.zone.value, macro_targets=nnv.macro_targets,
                  macro_weights=nnv.macro_weights,
                  micro_targets=nnv.micro_targets, priority_micros=nnv.priority_micros)


class FoodsResponse(BaseModel):
    foods: list[FoodOut]


@router.get("/api/foods", response_model=FoodsResponse)
def list_foods(store: FoodStore = Depends(get_store)) -> FoodsResponse:
    if store is None:
        raise HTTPException(status_code=503, detail="food store not configured")
    # Same pool the ranker scores, so catalog and recommendations share one universe.
    return FoodsResponse(foods=[_food_out(f) for f in store.candidates(limit=200)])


@router.post("/api/recommend", response_model=RecommendResponse)
def recommend_meals(
    req: RecommendRequest,
    store: FoodStore = Depends(get_store),
) -> RecommendResponse:
    if store is None:
        raise HTTPException(status_code=503, detail="food store not configured")
    try:
        zone = Zone(req.zone)
    except ValueError:
        raise HTTPException(status_code=422, detail=f"unknown zone: {req.zone}")
    if req.meal_type is not None and req.meal_type not in MEAL_ENERGY_FRACTIONS:
        raise HTTPException(status_code=422, detail=f"unknown meal_type: {req.meal_type}")
    profile = Profile(**req.profile.model_dump()) if req.profile else None
    nnv = build_nnv(zone, profile, req.meal_type)
    ranked = rank_foods(store.candidates(limit=200), nnv)[:10]
    meals = [
        MealOut(
            food=_food_out(food),
            enms=score,
            m_macro=macro_score(food, nnv),
            m_micro=micro_score(food, nnv),
            satisfied_targets=_satisfied_targets(food, nnv),
        )
        for food, score in ranked
    ]
    return RecommendResponse(meals=meals, nnv=_nnv_out(nnv))
