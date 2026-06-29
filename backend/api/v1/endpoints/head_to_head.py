"""Driver-vs-driver head-to-head comparison endpoint.

Compares every session both drivers were classified in (intersected by
session_key), optionally restricted to one championship year.
"""

from __future__ import annotations

from fastapi import APIRouter, Depends, Query
from sqlalchemy import select
from sqlalchemy.orm import Session

from backend.core.cache import make_key, response_cache
from backend.core.exceptions import InvalidQueryError, NotFoundError
from backend.dependencies import get_db
from backend.schemas.driver import DriverOut
from backend.schemas.head_to_head import HeadToHeadOut, HeadToHeadSessionOut
from models.driver import Driver
from models.result import Result
from models.session import Session as SessionModel

router = APIRouter(tags=["head-to-head"])


@router.get("/head-to-head", response_model=HeadToHeadOut)
def head_to_head(
    driver1: int = Query(..., description="First driver's number."),
    driver2: int = Query(..., description="Second driver's number."),
    year: int | None = Query(None, description="Restrict the comparison to one championship year."),
    db: Session = Depends(get_db),
) -> HeadToHeadOut:
    if driver1 == driver2:
        raise InvalidQueryError("driver1 and driver2 must be different drivers")

    key = make_key("head_to_head", driver1=driver1, driver2=driver2, year=year)
    cached = response_cache.get(key)
    if cached is not None:
        return cached

    d1 = db.get(Driver, driver1)
    d2 = db.get(Driver, driver2)
    if d1 is None:
        raise NotFoundError(f"driver {driver1} not found")
    if d2 is None:
        raise NotFoundError(f"driver {driver2} not found")

    r1_by_session = {r.session_key: r for r in db.scalars(select(Result).where(Result.driver_number == driver1))}
    r2_by_session = {r.session_key: r for r in db.scalars(select(Result).where(Result.driver_number == driver2))}
    shared_session_keys = set(r1_by_session) & set(r2_by_session)

    sessions_by_key = {
        s.session_key: s
        for s in db.scalars(select(SessionModel).where(SessionModel.session_key.in_(shared_session_keys)))
        if year is None or s.year == year
    }

    sessions_out: list[HeadToHeadSessionOut] = []
    driver1_ahead = driver2_ahead = 0
    driver1_points_total = driver2_points_total = 0.0

    for session_key, session in sorted(sessions_by_key.items()):
        res1, res2 = r1_by_session[session_key], r2_by_session[session_key]
        if res1.position is not None and res2.position is not None:
            if res1.position < res2.position:
                driver1_ahead += 1
            elif res2.position < res1.position:
                driver2_ahead += 1
        driver1_points_total += res1.points or 0.0
        driver2_points_total += res2.points or 0.0
        sessions_out.append(
            HeadToHeadSessionOut(
                session_key=session_key,
                session_name=session.session_name,
                year=session.year,
                driver1_position=res1.position,
                driver2_position=res2.position,
                driver1_points=res1.points,
                driver2_points=res2.points,
            )
        )

    result = HeadToHeadOut(
        driver1=DriverOut.model_validate(d1),
        driver2=DriverOut.model_validate(d2),
        sessions_compared=len(sessions_out),
        driver1_ahead=driver1_ahead,
        driver2_ahead=driver2_ahead,
        driver1_points_total=driver1_points_total,
        driver2_points_total=driver2_points_total,
        sessions=sessions_out,
    )
    response_cache.set(key, result)
    return result
