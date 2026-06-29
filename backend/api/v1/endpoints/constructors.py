"""Constructor (team) list endpoint."""

from __future__ import annotations

from fastapi import APIRouter, Depends
from sqlalchemy import select
from sqlalchemy.orm import Session

from backend.core.cache import make_key, response_cache
from backend.core.query import apply_sort, paginate
from backend.dependencies import Pagination, Sort, get_db, pagination_params, sort_params
from backend.schemas.common import Page
from backend.schemas.constructor import ConstructorOut
from models.constructor import Constructor
from models.driver import Driver

router = APIRouter(tags=["constructors"])

_SORTABLE_FIELDS = frozenset({"team_name"})
_sort_dependency = sort_params(_SORTABLE_FIELDS, default="team_name")


@router.get("/constructors", response_model=Page[ConstructorOut])
def list_constructors(
    pagination: Pagination = Depends(pagination_params),
    sort: Sort = Depends(_sort_dependency),
    db: Session = Depends(get_db),
) -> Page[ConstructorOut]:
    key = make_key(
        "constructors",
        page=pagination.page,
        page_size=pagination.page_size,
        sort=sort.field,
        desc=sort.descending,
    )
    cached = response_cache.get(key)
    if cached is not None:
        return cached

    stmt = select(Constructor)
    stmt = apply_sort(stmt, Constructor, sort)
    rows, total = paginate(db, stmt, pagination)

    drivers_by_team: dict[str, list[int]] = {}
    for team_name, driver_number in db.execute(select(Driver.team_name, Driver.driver_number)):
        if team_name:
            drivers_by_team.setdefault(team_name, []).append(driver_number)

    items = [
        ConstructorOut(
            team_name=c.team_name,
            team_colour=c.team_colour,
            driver_numbers=sorted(drivers_by_team.get(c.team_name, [])),
        )
        for c in rows
    ]
    page = Page.create(items, total, pagination.page, pagination.page_size)
    response_cache.set(key, page)
    return page
