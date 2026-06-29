"""Driver position-over-time samples within a session.

Distinct from `Result.position` (the final classification): this table
records every position change as it happens during the session.
"""

from __future__ import annotations

import datetime as dt
from typing import TYPE_CHECKING

from sqlalchemy import CheckConstraint, ForeignKey, Index, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from database.base import Base

if TYPE_CHECKING:
    from models.driver import Driver
    from models.session import Session


class Position(Base):
    __tablename__ = "positions"
    __table_args__ = (
        UniqueConstraint(
            "session_key", "driver_number", "date", name="uq_positions_session_driver_date"
        ),
        Index("ix_positions_session_key", "session_key"),
        Index("ix_positions_driver_number", "driver_number"),
        CheckConstraint("position > 0", name="ck_positions_position_positive"),
    )

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    session_key: Mapped[int] = mapped_column(ForeignKey("sessions.session_key"))
    driver_number: Mapped[int] = mapped_column(ForeignKey("drivers.driver_number"))
    date: Mapped[dt.datetime] = mapped_column()
    position: Mapped[int] = mapped_column()

    session: Mapped[Session] = relationship(back_populates="positions")
    driver: Mapped[Driver] = relationship(back_populates="positions")
