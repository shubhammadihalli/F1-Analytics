"""Team radio messages exchanged between a driver and their pit wall."""

from __future__ import annotations

import datetime as dt
from typing import TYPE_CHECKING

from sqlalchemy import ForeignKey, Index, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from database.base import Base

if TYPE_CHECKING:
    from models.driver import Driver
    from models.session import Session


class Message(Base):
    __tablename__ = "messages"
    __table_args__ = (
        UniqueConstraint(
            "session_key", "driver_number", "date", name="uq_messages_session_driver_date"
        ),
        Index("ix_messages_session_key", "session_key"),
        Index("ix_messages_driver_number", "driver_number"),
    )

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    session_key: Mapped[int] = mapped_column(ForeignKey("sessions.session_key"))
    driver_number: Mapped[int] = mapped_column(ForeignKey("drivers.driver_number"))
    date: Mapped[dt.datetime] = mapped_column()
    recording_url: Mapped[str | None] = mapped_column()

    session: Mapped[Session] = relationship(back_populates="radio_messages")
    driver: Mapped[Driver] = relationship(back_populates="radio_messages")
