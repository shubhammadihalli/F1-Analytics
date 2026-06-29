"""Cumulative constructor championship standing for a season, derived from results."""

from __future__ import annotations

from typing import TYPE_CHECKING

from sqlalchemy import CheckConstraint, ForeignKey, Index
from sqlalchemy.orm import Mapped, mapped_column, relationship

from database.base import Base

if TYPE_CHECKING:
    from models.constructor import Constructor
    from models.season import Season


class ConstructorStanding(Base):
    __tablename__ = "constructor_standings"
    __table_args__ = (
        Index("ix_constructor_standings_team_name", "team_name"),
        CheckConstraint("points >= 0", name="ck_constructor_standings_points_non_negative"),
        CheckConstraint("wins >= 0", name="ck_constructor_standings_wins_non_negative"),
        CheckConstraint(
            "position IS NULL OR position > 0", name="ck_constructor_standings_position_positive"
        ),
    )

    year: Mapped[int] = mapped_column(ForeignKey("seasons.year"), primary_key=True)
    team_name: Mapped[str] = mapped_column(ForeignKey("constructors.team_name"), primary_key=True)
    points: Mapped[float] = mapped_column(default=0)
    wins: Mapped[int] = mapped_column(default=0)
    position: Mapped[int | None] = mapped_column()

    season: Mapped[Season] = relationship(back_populates="constructor_standings")
    constructor: Mapped[Constructor] = relationship(back_populates="standings")
