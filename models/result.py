"""Per-driver classification for a single race weekend session."""

from __future__ import annotations

from typing import TYPE_CHECKING

from sqlalchemy import CheckConstraint, ForeignKey, Index
from sqlalchemy.orm import Mapped, mapped_column, relationship

from database.base import Base

if TYPE_CHECKING:
    from models.driver import Driver
    from models.session import Session


class Result(Base):
    __tablename__ = "results"
    __table_args__ = (
        Index("ix_results_driver_number", "driver_number"),
        CheckConstraint("position IS NULL OR position > 0", name="ck_results_position_positive"),
        CheckConstraint("points IS NULL OR points >= 0", name="ck_results_points_non_negative"),
    )

    session_key: Mapped[int] = mapped_column(ForeignKey("sessions.session_key"), primary_key=True)
    driver_number: Mapped[int] = mapped_column(ForeignKey("drivers.driver_number"), primary_key=True)
    position: Mapped[int | None] = mapped_column()
    number_of_laps: Mapped[int | None] = mapped_column()
    points: Mapped[float | None] = mapped_column()
    dnf: Mapped[bool] = mapped_column(default=False)
    dns: Mapped[bool] = mapped_column(default=False)
    dsq: Mapped[bool] = mapped_column(default=False)
    duration: Mapped[float | None] = mapped_column()
    gap_to_leader: Mapped[float | None] = mapped_column()

    session: Mapped[Session] = relationship(back_populates="results")
    driver: Mapped[Driver] = relationship(back_populates="results")
