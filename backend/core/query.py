"""Generic helpers for paginating and sorting a SQLAlchemy `Select`."""

from __future__ import annotations

from typing import Any

from sqlalchemy import Select, func, select
from sqlalchemy.orm import InstrumentedAttribute, Session

from backend.dependencies import Pagination, Sort


def apply_sort(stmt: Select[Any], model: type[Any], sort: Sort) -> Select[Any]:
    column: InstrumentedAttribute[Any] = getattr(model, sort.field)
    return stmt.order_by(column.desc() if sort.descending else column.asc())


def paginate(db: Session, stmt: Select[Any], pagination: Pagination) -> tuple[list[Any], int]:
    """Run `stmt` with LIMIT/OFFSET applied, plus a matching total-row count."""
    total = db.scalar(select(func.count()).select_from(stmt.order_by(None).subquery())) or 0
    rows = list(db.scalars(stmt.offset(pagination.offset).limit(pagination.page_size)))
    return rows, total
