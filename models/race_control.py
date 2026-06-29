"""Race control messages (flags, safety car, incidents, etc.) for a session."""

from __future__ import annotations

import datetime as dt
from typing import TYPE_CHECKING

from sqlalchemy import ForeignKey, Index
from sqlalchemy.orm import Mapped, mapped_column, relationship

from database.base import Base

if TYPE_CHECKING:
    from models.driver import Driver
    from models.session import Session


class RaceControlMessage(Base):
    __tablename__ = "race_control"
    __table_args__ = (
        Index("ix_race_control_session_key", "session_key"),
        Index("ix_race_control_category", "category"),
    )

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    session_key: Mapped[int] = mapped_column(ForeignKey("sessions.session_key"))
    driver_number: Mapped[int | None] = mapped_column(ForeignKey("drivers.driver_number"))
    date: Mapped[dt.datetime] = mapped_column()
    category: Mapped[str | None] = mapped_column()
    flag: Mapped[str | None] = mapped_column()
    scope: Mapped[str | None] = mapped_column()
    sector: Mapped[int | None] = mapped_column()
    lap_number: Mapped[int | None] = mapped_column()
    message: Mapped[str | None] = mapped_column()

    session: Mapped[Session] = relationship(back_populates="race_control_messages")
    driver: Mapped[Driver | None] = relationship(back_populates="race_control_messages")
