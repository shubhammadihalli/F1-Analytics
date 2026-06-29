"""Pit lane stop timing for a driver within a session."""

from __future__ import annotations

import datetime as dt
from typing import TYPE_CHECKING

from sqlalchemy import CheckConstraint, ForeignKey, Index
from sqlalchemy.orm import Mapped, mapped_column, relationship

from database.base import Base

if TYPE_CHECKING:
    from models.driver import Driver
    from models.session import Session


class PitStop(Base):
    __tablename__ = "pit_stops"
    __table_args__ = (
        Index("ix_pit_stops_driver_number", "driver_number"),
        CheckConstraint("lap_number > 0", name="ck_pit_stops_lap_number_positive"),
    )

    session_key: Mapped[int] = mapped_column(ForeignKey("sessions.session_key"), primary_key=True)
    driver_number: Mapped[int] = mapped_column(ForeignKey("drivers.driver_number"), primary_key=True)
    lap_number: Mapped[int] = mapped_column(primary_key=True)
    date: Mapped[dt.datetime | None] = mapped_column()
    pit_duration: Mapped[float | None] = mapped_column()
    stop_duration: Mapped[float | None] = mapped_column()
    lane_duration: Mapped[float | None] = mapped_column()

    session: Mapped[Session] = relationship(back_populates="pit_stops")
    driver: Mapped[Driver] = relationship(back_populates="pit_stops")
