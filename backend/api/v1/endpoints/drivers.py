"""Driver list and detail endpoints."""

from __future__ import annotations

from fastapi import APIRouter, Depends, Query
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from backend.core.cache import make_key, response_cache
from backend.core.exceptions import NotFoundError
from backend.core.query import apply_sort, paginate
from backend.dependencies import Pagination, Sort, get_db, pagination_params, sort_params
from backend.schemas.common import Page
from backend.schemas.driver import DriverCareerStatsOut, DriverDetailOut, DriverOut
from backend.schemas.standing import StandingOut
from models.driver import Driver
from models.driver_standing import DriverStanding
from models.result import Result
from models.session import Session as SessionModel

router = APIRouter(tags=["drivers"])

_SORTABLE_FIELDS = frozenset({"driver_number", "full_name", "team_name", "country_code"})
_sort_dependency = sort_params(_SORTABLE_FIELDS, default="driver_number")


@router.get("/drivers", response_model=Page[DriverOut])
def list_drivers(
    team_name: str | None = Query(None, description="Filter by constructor name."),
    country_code: str | None = Query(None, description="Filter by 3-letter country code."),
    pagination: Pagination = Depends(pagination_params),
    sort: Sort = Depends(_sort_dependency),
    db: Session = Depends(get_db),
) -> Page[DriverOut]:
    key = make_key(
        "drivers",
        team_name=team_name,
        country_code=country_code,
        page=pagination.page,
        page_size=pagination.page_size,
        sort=sort.field,
        desc=sort.descending,
    )
    cached = response_cache.get(key)
    if cached is not None:
        return cached

    stmt = select(Driver)
    if team_name is not None:
        stmt = stmt.where(Driver.team_name == team_name)
    if country_code is not None:
        stmt = stmt.where(Driver.country_code == country_code)
    stmt = apply_sort(stmt, Driver, sort)

    rows, total = paginate(db, stmt, pagination)
    page = Page.create(
        [DriverOut.model_validate(r) for r in rows], total, pagination.page, pagination.page_size
    )
    response_cache.set(key, page)
    return page


@router.get("/driver/{driver_number}", response_model=DriverDetailOut)
def get_driver(driver_number: int, db: Session = Depends(get_db)) -> DriverDetailOut:
    key = make_key("driver_detail", driver_number=driver_number)
    cached = response_cache.get(key)
    if cached is not None:
        return cached

    driver = db.get(Driver, driver_number)
    if driver is None:
        raise NotFoundError(f"driver {driver_number} not found")

    # Restricted to Race/Sprint sessions: counting qualifying pole positions
    # or practice session-bests as "wins"/"podiums" would be misleading.
    stats = db.execute(
        select(
            func.count(Result.session_key).label("races_entered"),
            func.count(Result.session_key).filter(Result.position == 1).label("wins"),
            func.count(Result.session_key).filter(Result.position <= 3).label("podiums"),
            func.coalesce(func.sum(Result.points), 0.0).label("points_total"),
        )
        .join(SessionModel, SessionModel.session_key == Result.session_key)
        .where(Result.driver_number == driver_number, SessionModel.session_type.in_(["Race", "Sprint"]))
    ).one()

    standings = [
        StandingOut(
            type="driver",
            year=s.year,
            position=s.position,
            points=s.points,
            wins=s.wins,
            driver_number=driver.driver_number,
            full_name=driver.full_name,
            team_name=driver.team_name,
        )
        for s in db.scalars(
            select(DriverStanding)
            .where(DriverStanding.driver_number == driver_number)
            .order_by(DriverStanding.year)
        )
    ]

    detail = DriverDetailOut(
        **DriverOut.model_validate(driver).model_dump(),
        career_stats=DriverCareerStatsOut(
            races_entered=stats.races_entered,
            wins=stats.wins,
            podiums=stats.podiums,
            points_total=float(stats.points_total),
        ),
        standings=standings,
    )
    response_cache.set(key, detail)
    return detail
