"""Lap-by-lap timing for a driver within a session."""

from __future__ import annotations

import datetime as dt
from typing import TYPE_CHECKING

from sqlalchemy import CheckConstraint, ForeignKey, Index
from sqlalchemy.orm import Mapped, mapped_column, relationship

from database.base import Base

if TYPE_CHECKING:
    from models.driver import Driver
    from models.session import Session


class Lap(Base):
    __tablename__ = "laps"
    __table_args__ = (
        Index("ix_laps_driver_number", "driver_number"),
        CheckConstraint("lap_number > 0", name="ck_laps_lap_number_positive"),
    )

    session_key: Mapped[int] = mapped_column(ForeignKey("sessions.session_key"), primary_key=True)
    driver_number: Mapped[int] = mapped_column(ForeignKey("drivers.driver_number"), primary_key=True)
    lap_number: Mapped[int] = mapped_column(primary_key=True)
    date_start: Mapped[dt.datetime | None] = mapped_column()
    lap_duration: Mapped[float | None] = mapped_column()
    duration_sector_1: Mapped[float | None] = mapped_column()
    duration_sector_2: Mapped[float | None] = mapped_column()
    duration_sector_3: Mapped[float | None] = mapped_column()
    i1_speed: Mapped[int | None] = mapped_column()
    i2_speed: Mapped[int | None] = mapped_column()
    st_speed: Mapped[int | None] = mapped_column()
    is_pit_out_lap: Mapped[bool] = mapped_column(default=False)

    session: Mapped[Session] = relationship(back_populates="laps")
    driver: Mapped[Driver] = relationship(back_populates="laps")
