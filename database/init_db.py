"""Dev convenience helper to create all tables without running Alembic."""

from __future__ import annotations

import models  # noqa: F401 - registers all mapped classes on Base.metadata
from database.base import Base
from database.session import engine


def init_db() -> None:
    Base.metadata.create_all(bind=engine)


if __name__ == "__main__":
    init_db()
