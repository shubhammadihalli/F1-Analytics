"""Shared FastAPI dependencies: DB sessions, pagination, and sorting."""

from __future__ import annotations

from collections.abc import Callable, Generator
from dataclasses import dataclass

from fastapi import Query
from sqlalchemy.orm import Session

from backend.core.config import settings
from backend.core.exceptions import InvalidQueryError
from database.session import SessionLocal


def get_db() -> Generator[Session, None, None]:
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


@dataclass(frozen=True)
class Pagination:
    page: int
    page_size: int

    @property
    def offset(self) -> int:
        return (self.page - 1) * self.page_size


def pagination_params(
    page: int = Query(1, ge=1, description="1-indexed page number."),
    page_size: int = Query(
        settings.default_page_size,
        ge=1,
        le=settings.max_page_size,
        description="Rows per page.",
    ),
) -> Pagination:
    return Pagination(page=page, page_size=page_size)


@dataclass(frozen=True)
class Sort:
    field: str
    descending: bool


def sort_params(allowed_fields: frozenset[str], default: str) -> Callable[[str], Sort]:
    """Build a FastAPI dependency validating `sort` against `allowed_fields`.

    `sort` is a field name, optionally prefixed with `-` for descending order
    (e.g. `-points`). An unknown field is rejected with a 422 instead of
    being silently ignored or passed straight through to SQL.
    """

    def _dependency(
        sort: str = Query(
            default,
            description=f"Sort field, prefix with '-' for descending. One of: {', '.join(sorted(allowed_fields))}.",
        ),
    ) -> Sort:
        descending = sort.startswith("-")
        field = sort[1:] if descending else sort
        if field not in allowed_fields:
            raise InvalidQueryError(
                f"invalid sort field '{field}'; must be one of {sorted(allowed_fields)}"
            )
        return Sort(field=field, descending=descending)

    return _dependency
