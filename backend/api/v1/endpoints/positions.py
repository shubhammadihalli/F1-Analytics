"""Driver position-over-time endpoint, used for race-replay style visualizations."""

from __future__ import annotations

from fastapi import APIRouter, Depends, Query
from sqlalchemy import select
from sqlalchemy.orm import Session

from backend.core.cache import make_key, response_cache
from backend.core.query import apply_sort, paginate
from backend.dependencies import Pagination, Sort, get_db, pagination_params, sort_params
from backend.schemas.common import Page
from backend.schemas.position import PositionOut
from models.position import Position

router = APIRouter(tags=["positions"])

_SORTABLE_FIELDS = frozenset({"date", "position"})
_sort_dependency = sort_params(_SORTABLE_FIELDS, default="date")


@router.get("/positions", response_model=Page[PositionOut])
def list_positions(
    session_key: int = Query(..., description="Session to fetch position history for (required)."),
    driver_number: int | None = Query(None, description="Filter by driver."),
    pagination: Pagination = Depends(pagination_params),
    sort: Sort = Depends(_sort_dependency),
    db: Session = Depends(get_db),
) -> Page[PositionOut]:
    key = make_key(
        "positions",
        session_key=session_key,
        driver_number=driver_number,
        page=pagination.page,
        page_size=pagination.page_size,
        sort=sort.field,
        desc=sort.descending,
    )
    cached = response_cache.get(key)
    if cached is not None:
        return cached

    stmt = select(Position).where(Position.session_key == session_key)
    if driver_number is not None:
        stmt = stmt.where(Position.driver_number == driver_number)
    stmt = apply_sort(stmt, Position, sort)

    rows, total = paginate(db, stmt, pagination)
    page = Page.create(
        [PositionOut.model_validate(r) for r in rows], total, pagination.page, pagination.page_size
    )
    response_cache.set(key, page)
    return page
