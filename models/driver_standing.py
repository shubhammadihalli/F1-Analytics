"""Cumulative driver championship standing for a season, derived from results."""

from __future__ import annotations

from typing import TYPE_CHECKING

from sqlalchemy import CheckConstraint, ForeignKey, Index
from sqlalchemy.orm import Mapped, mapped_column, relationship

from database.base import Base

if TYPE_CHECKING:
    from models.driver import Driver
    from models.season import Season


class DriverStanding(Base):
    __tablename__ = "driver_standings"
    __table_args__ = (
        Index("ix_driver_standings_driver_number", "driver_number"),
        CheckConstraint("points >= 0", name="ck_driver_standings_points_non_negative"),
        CheckConstraint("wins >= 0", name="ck_driver_standings_wins_non_negative"),
        CheckConstraint("position IS NULL OR position > 0", name="ck_driver_standings_position_positive"),
    )

    year: Mapped[int] = mapped_column(ForeignKey("seasons.year"), primary_key=True)
    driver_number: Mapped[int] = mapped_column(ForeignKey("drivers.driver_number"), primary_key=True)
    points: Mapped[float] = mapped_column(default=0)
    wins: Mapped[int] = mapped_column(default=0)
    position: Mapped[int | None] = mapped_column()

    season: Mapped[Season] = relationship(back_populates="driver_standings")
    driver: Mapped[Driver] = relationship(back_populates="standings")
