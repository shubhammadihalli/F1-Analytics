"""Constructor (team) model.

OpenF1 exposes no stable numeric team id, so the team name is the natural
primary key.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from sqlalchemy.orm import Mapped, mapped_column, relationship

from database.base import Base

if TYPE_CHECKING:
    from models.constructor_standing import ConstructorStanding
    from models.driver import Driver


class Constructor(Base):
    __tablename__ = "constructors"

    team_name: Mapped[str] = mapped_column(primary_key=True)
    team_colour: Mapped[str | None] = mapped_column()

    drivers: Mapped[list[Driver]] = relationship(back_populates="constructor")
    standings: Mapped[list[ConstructorStanding]] = relationship(back_populates="constructor")
