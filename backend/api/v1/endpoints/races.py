"""Race weekend session list endpoint.

Exposed at `/races` though it covers every session type (practice through
race) since that's the only place this data lives; filter by `session_type`
to narrow to races specifically.
"""

from __future__ import annotations

from fastapi import APIRouter, Depends, Query
from sqlalchemy import select
from sqlalchemy.orm import Session

from backend.core.cache import make_key, response_cache
from backend.core.query import apply_sort, paginate
from backend.dependencies import Pagination, Sort, get_db, pagination_params, sort_params
from backend.schemas.common import Page
from backend.schemas.race import RaceOut
from models.circuit import Circuit
from models.session import Session as SessionModel

router = APIRouter(tags=["races"])

_SORTABLE_FIELDS = frozenset({"session_key", "date_start", "year", "session_type"})
_sort_dependency = sort_params(_SORTABLE_FIELDS, default="-date_start")


@router.get("/races", response_model=Page[RaceOut])
def list_races(
    year: int | None = Query(None, description="Filter by championship year."),
    session_type: str | None = Query(
        None, description="Filter by session type, e.g. 'Race', 'Qualifying', 'Practice 1'."
    ),
    circuit_key: int | None = Query(None, description="Filter by circuit."),
    pagination: Pagination = Depends(pagination_params),
    sort: Sort = Depends(_sort_dependency),
    db: Session = Depends(get_db),
) -> Page[RaceOut]:
    key = make_key(
        "races",
        year=year,
        session_type=session_type,
        circuit_key=circuit_key,
        page=pagination.page,
        page_size=pagination.page_size,
        sort=sort.field,
        desc=sort.descending,
    )
    cached = response_cache.get(key)
    if cached is not None:
        return cached

    stmt = select(SessionModel)
    if year is not None:
        stmt = stmt.where(SessionModel.year == year)
    if session_type is not None:
        stmt = stmt.where(SessionModel.session_type == session_type)
    if circuit_key is not None:
        stmt = stmt.where(SessionModel.circuit_key == circuit_key)
    stmt = apply_sort(stmt, SessionModel, sort)

    rows, total = paginate(db, stmt, pagination)

    circuit_names: dict[int, str | None] = {
        key: name for key, name in db.execute(select(Circuit.circuit_key, Circuit.circuit_short_name))
    }
    items = [
        RaceOut(
            session_key=r.session_key,
            meeting_key=r.meeting_key,
            circuit_key=r.circuit_key,
            circuit_short_name=circuit_names.get(r.circuit_key) if r.circuit_key else None,
            year=r.year,
            session_type=r.session_type,
            session_name=r.session_name,
            date_start=r.date_start,
            date_end=r.date_end,
            is_cancelled=r.is_cancelled,
        )
        for r in rows
    ]
    page = Page.create(items, total, pagination.page, pagination.page_size)
    response_cache.set(key, page)
    return page
