"""Starting grid position for a Race or Sprint session, sourced from the
preceding Qualifying/Sprint Qualifying session within the same meeting.

OpenF1's `/starting_grid` endpoint keys its rows to the *qualifying*
session's session_key, not the race's - the ETL resolves that mapping once
at ingest time so this table can be queried directly by the race's own
session_key, matching how every other per-race table works.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from sqlalchemy import CheckConstraint, ForeignKey, Index, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from database.base import Base

if TYPE_CHECKING:
    from models.driver import Driver
    from models.session import Session


class StartingGridPosition(Base):
    __tablename__ = "starting_grids"
    __table_args__ = (
        UniqueConstraint("session_key", "driver_number", name="uq_starting_grids_session_driver"),
        Index("ix_starting_grids_session_key", "session_key"),
        CheckConstraint("grid_position > 0", name="ck_starting_grids_position_positive"),
    )

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    session_key: Mapped[int] = mapped_column(ForeignKey("sessions.session_key"))
    driver_number: Mapped[int] = mapped_column(ForeignKey("drivers.driver_number"))
    grid_position: Mapped[int] = mapped_column()
    qualifying_lap_duration: Mapped[float | None] = mapped_column()

    session: Mapped[Session] = relationship(back_populates="starting_grid_positions")
    driver: Mapped[Driver] = relationship(back_populates="starting_grid_positions")
