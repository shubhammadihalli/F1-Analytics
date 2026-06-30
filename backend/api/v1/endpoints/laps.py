"""Lap-by-lap timing endpoint."""

from __future__ import annotations

from fastapi import APIRouter, Depends, Query
from sqlalchemy import select
from sqlalchemy.orm import Session

from backend.core.cache import make_key, response_cache
from backend.core.query import apply_sort, paginate
from backend.dependencies import Pagination, Sort, get_db, pagination_params, sort_params
from backend.schemas.common import Page
from backend.schemas.lap import LapOut
from models.lap import Lap
from models.session import Session as SessionModel

router = APIRouter(tags=["laps"])

_SORTABLE_FIELDS = frozenset({"lap_number", "lap_duration", "date_start"})
_sort_dependency = sort_params(_SORTABLE_FIELDS, default="lap_number")


@router.get("/laps", response_model=Page[LapOut])
def list_laps(
    session_key: int | None = Query(None, description="Filter by session."),
    driver_number: int | None = Query(None, description="Filter by driver."),
    lap_number: int | None = Query(None, description="Filter by lap number."),
    year: int | None = Query(None, description="Filter by championship year."),
    session_type: str | None = Query(
        None, description="Filter by session type, e.g. 'Race', 'Qualifying'."
    ),
    pagination: Pagination = Depends(pagination_params),
    sort: Sort = Depends(_sort_dependency),
    db: Session = Depends(get_db),
) -> Page[LapOut]:
    key = make_key(
        "laps",
        session_key=session_key,
        driver_number=driver_number,
        lap_number=lap_number,
        year=year,
        session_type=session_type,
        page=pagination.page,
        page_size=pagination.page_size,
        sort=sort.field,
        desc=sort.descending,
    )
    cached = response_cache.get(key)
    if cached is not None:
        return cached

    stmt = select(Lap)
    if session_key is not None:
        stmt = stmt.where(Lap.session_key == session_key)
    if driver_number is not None:
        stmt = stmt.where(Lap.driver_number == driver_number)
    if lap_number is not None:
        stmt = stmt.where(Lap.lap_number == lap_number)
    if year is not None or session_type is not None:
        stmt = stmt.join(SessionModel, SessionModel.session_key == Lap.session_key)
        if year is not None:
            stmt = stmt.where(SessionModel.year == year)
        if session_type is not None:
            stmt = stmt.where(SessionModel.session_type == session_type)
    stmt = apply_sort(stmt, Lap, sort)

    rows, total = paginate(db, stmt, pagination)
    page = Page.create(
        [LapOut.model_validate(r) for r in rows], total, pagination.page, pagination.page_size
    )
    response_cache.set(key, page)
    return page
