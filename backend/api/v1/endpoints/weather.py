"""Track/air weather sample endpoint."""

from __future__ import annotations

from fastapi import APIRouter, Depends, Query
from sqlalchemy import select
from sqlalchemy.orm import Session

from backend.core.cache import make_key, response_cache
from backend.core.query import apply_sort, paginate
from backend.dependencies import Pagination, Sort, get_db, pagination_params, sort_params
from backend.schemas.common import Page
from backend.schemas.weather import WeatherOut
from models.weather import Weather

router = APIRouter(tags=["weather"])

_SORTABLE_FIELDS = frozenset({"date", "air_temperature", "track_temperature", "rainfall"})
_sort_dependency = sort_params(_SORTABLE_FIELDS, default="date")


@router.get("/weather", response_model=Page[WeatherOut])
def list_weather(
    session_key: int | None = Query(None, description="Filter by session."),
    pagination: Pagination = Depends(pagination_params),
    sort: Sort = Depends(_sort_dependency),
    db: Session = Depends(get_db),
) -> Page[WeatherOut]:
    key = make_key(
        "weather",
        session_key=session_key,
        page=pagination.page,
        page_size=pagination.page_size,
        sort=sort.field,
        desc=sort.descending,
    )
    cached = response_cache.get(key)
    if cached is not None:
        return cached

    stmt = select(Weather)
    if session_key is not None:
        stmt = stmt.where(Weather.session_key == session_key)
    stmt = apply_sort(stmt, Weather, sort)

    rows, total = paginate(db, stmt, pagination)
    page = Page.create(
        [WeatherOut.model_validate(r) for r in rows], total, pagination.page, pagination.page_size
    )
    response_cache.set(key, page)
    return page
