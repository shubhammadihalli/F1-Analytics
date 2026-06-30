"""Starting grid position endpoint."""

from __future__ import annotations

from fastapi import APIRouter, Depends, Query
from sqlalchemy import select
from sqlalchemy.orm import Session

from backend.core.cache import make_key, response_cache
from backend.core.query import apply_sort, paginate
from backend.dependencies import Pagination, Sort, get_db, pagination_params, sort_params
from backend.schemas.common import Page
from backend.schemas.starting_grid import StartingGridOut
from models.starting_grid import StartingGridPosition

router = APIRouter(tags=["starting-grid"])

_SORTABLE_FIELDS = frozenset({"grid_position", "qualifying_lap_duration"})
_sort_dependency = sort_params(_SORTABLE_FIELDS, default="grid_position")


@router.get("/starting-grid", response_model=Page[StartingGridOut])
def list_starting_grid(
    session_key: int = Query(..., description="Race/Sprint session to fetch the grid for (required)."),
    pagination: Pagination = Depends(pagination_params),
    sort: Sort = Depends(_sort_dependency),
    db: Session = Depends(get_db),
) -> Page[StartingGridOut]:
    key = make_key(
        "starting_grid",
        session_key=session_key,
        page=pagination.page,
        page_size=pagination.page_size,
        sort=sort.field,
        desc=sort.descending,
    )
    cached = response_cache.get(key)
    if cached is not None:
        return cached

    stmt = select(StartingGridPosition).where(StartingGridPosition.session_key == session_key)
    stmt = apply_sort(stmt, StartingGridPosition, sort)

    rows, total = paginate(db, stmt, pagination)
    page = Page.create(
        [StartingGridOut.model_validate(r) for r in rows], total, pagination.page, pagination.page_size
    )
    response_cache.set(key, page)
    return page
