"""Car telemetry endpoint.

`session_key` and `driver_number` are both required: OpenF1's own API
rejects whole-session telemetry requests as "too much data at once", and the
same constraint holds here - a single driver's session can be 30k+ rows.
"""

from __future__ import annotations

from fastapi import APIRouter, Depends, Query
from sqlalchemy import select
from sqlalchemy.orm import Session

from backend.core.cache import make_key, response_cache
from backend.core.query import apply_sort, paginate
from backend.dependencies import Pagination, Sort, get_db, pagination_params, sort_params
from backend.schemas.common import Page
from backend.schemas.telemetry import TelemetryOut
from models.telemetry import Telemetry

router = APIRouter(tags=["telemetry"])

_SORTABLE_FIELDS = frozenset({"date", "speed", "rpm", "throttle", "brake"})
_sort_dependency = sort_params(_SORTABLE_FIELDS, default="date")


@router.get("/telemetry", response_model=Page[TelemetryOut])
def list_telemetry(
    session_key: int = Query(..., description="Session to fetch telemetry for (required)."),
    driver_number: int = Query(..., description="Driver to fetch telemetry for (required)."),
    pagination: Pagination = Depends(pagination_params),
    sort: Sort = Depends(_sort_dependency),
    db: Session = Depends(get_db),
) -> Page[TelemetryOut]:
    key = make_key(
        "telemetry",
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

    stmt = select(Telemetry).where(
        Telemetry.session_key == session_key, Telemetry.driver_number == driver_number
    )
    stmt = apply_sort(stmt, Telemetry, sort)

    rows, total = paginate(db, stmt, pagination)
    page = Page.create(
        [TelemetryOut.model_validate(r) for r in rows], total, pagination.page, pagination.page_size
    )
    response_cache.set(key, page)
    return page
