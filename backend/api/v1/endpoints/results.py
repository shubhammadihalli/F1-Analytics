"""Per-session driver classification endpoint."""

from __future__ import annotations

from fastapi import APIRouter, Depends, Query
from sqlalchemy import select
from sqlalchemy.orm import Session

from backend.core.cache import make_key, response_cache
from backend.core.query import apply_sort, paginate
from backend.dependencies import Pagination, Sort, get_db, pagination_params, sort_params
from backend.schemas.common import Page
from backend.schemas.result import ResultOut
from models.result import Result

router = APIRouter(tags=["results"])

_SORTABLE_FIELDS = frozenset({"position", "points", "driver_number"})
_sort_dependency = sort_params(_SORTABLE_FIELDS, default="position")


@router.get("/results", response_model=Page[ResultOut])
def list_results(
    session_key: int | None = Query(None, description="Filter by session."),
    driver_number: int | None = Query(None, description="Filter by driver."),
    pagination: Pagination = Depends(pagination_params),
    sort: Sort = Depends(_sort_dependency),
    db: Session = Depends(get_db),
) -> Page[ResultOut]:
    key = make_key(
        "results",
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

    stmt = select(Result)
    if session_key is not None:
        stmt = stmt.where(Result.session_key == session_key)
    if driver_number is not None:
        stmt = stmt.where(Result.driver_number == driver_number)
    stmt = apply_sort(stmt, Result, sort)

    rows, total = paginate(db, stmt, pagination)
    page = Page.create(
        [ResultOut.model_validate(r) for r in rows], total, pagination.page, pagination.page_size
    )
    response_cache.set(key, page)
    return page
