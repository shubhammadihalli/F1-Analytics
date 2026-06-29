"""Weather samples recorded periodically throughout a session."""

from __future__ import annotations

import datetime as dt
from typing import TYPE_CHECKING

from sqlalchemy import ForeignKey, Index, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from database.base import Base

if TYPE_CHECKING:
    from models.session import Session


class Weather(Base):
    __tablename__ = "weather"
    __table_args__ = (
        UniqueConstraint("session_key", "date", name="uq_weather_session_date"),
        Index("ix_weather_session_key", "session_key"),
    )

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    session_key: Mapped[int] = mapped_column(ForeignKey("sessions.session_key"))
    date: Mapped[dt.datetime] = mapped_column()
    air_temperature: Mapped[float | None] = mapped_column()
    track_temperature: Mapped[float | None] = mapped_column()
    humidity: Mapped[float | None] = mapped_column()
    pressure: Mapped[float | None] = mapped_column()
    rainfall: Mapped[float | None] = mapped_column()
    wind_direction: Mapped[int | None] = mapped_column()
    wind_speed: Mapped[float | None] = mapped_column()

    session: Mapped[Session] = relationship(back_populates="weather_samples")
