"""Tyre stint data: which compound a driver ran, and for which laps, within a session."""

from __future__ import annotations

from typing import TYPE_CHECKING

from sqlalchemy import CheckConstraint, ForeignKey, Index, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from database.base import Base

if TYPE_CHECKING:
    from models.driver import Driver
    from models.session import Session


class Stint(Base):
    __tablename__ = "stints"
    __table_args__ = (
        UniqueConstraint(
            "session_key", "driver_number", "stint_number", name="uq_stints_session_driver_stint"
        ),
        Index("ix_stints_session_driver", "session_key", "driver_number"),
        CheckConstraint("stint_number > 0", name="ck_stints_stint_number_positive"),
        CheckConstraint("lap_start > 0", name="ck_stints_lap_start_positive"),
        CheckConstraint("tyre_age_at_start >= 0", name="ck_stints_tyre_age_non_negative"),
    )

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    session_key: Mapped[int] = mapped_column(ForeignKey("sessions.session_key"))
    driver_number: Mapped[int] = mapped_column(ForeignKey("drivers.driver_number"))
    stint_number: Mapped[int] = mapped_column()
    compound: Mapped[str | None] = mapped_column()
    lap_start: Mapped[int] = mapped_column()
    lap_end: Mapped[int | None] = mapped_column()
    tyre_age_at_start: Mapped[int] = mapped_column(default=0)

    session: Mapped[Session] = relationship(back_populates="stints")
    driver: Mapped[Driver] = relationship(back_populates="stints")
