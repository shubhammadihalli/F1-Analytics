"""Season (F1 championship year) model."""

from __future__ import annotations

from typing import TYPE_CHECKING

from sqlalchemy.orm import Mapped, mapped_column, relationship

from database.base import Base

if TYPE_CHECKING:
    from models.constructor_standing import ConstructorStanding
    from models.driver_standing import DriverStanding
    from models.session import Session


class Season(Base):
    __tablename__ = "seasons"

    year: Mapped[int] = mapped_column(primary_key=True)

    sessions: Mapped[list[Session]] = relationship(back_populates="season")
    driver_standings: Mapped[list[DriverStanding]] = relationship(back_populates="season")
    constructor_standings: Mapped[list[ConstructorStanding]] = relationship(back_populates="season")
