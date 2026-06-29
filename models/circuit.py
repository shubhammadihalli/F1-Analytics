"""Circuit (track) model."""

from __future__ import annotations

from typing import TYPE_CHECKING

from sqlalchemy.orm import Mapped, mapped_column, relationship

from database.base import Base

if TYPE_CHECKING:
    from models.session import Session


class Circuit(Base):
    __tablename__ = "circuits"

    circuit_key: Mapped[int] = mapped_column(primary_key=True)
    circuit_short_name: Mapped[str | None] = mapped_column()
    country_code: Mapped[str | None] = mapped_column()
    country_name: Mapped[str | None] = mapped_column()
    location: Mapped[str | None] = mapped_column()

    sessions: Mapped[list[Session]] = relationship(back_populates="circuit")
