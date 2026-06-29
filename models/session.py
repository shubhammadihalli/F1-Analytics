"""Race weekend session model (practice, qualifying, sprint, or race).

`session_type` distinguishes practice from qualifying/sprint/race, so there
is no separate qualifying model.
"""

from __future__ import annotations

import datetime as dt
from typing import TYPE_CHECKING

from sqlalchemy import ForeignKey, Index
from sqlalchemy.orm import Mapped, mapped_column, relationship

from database.base import Base

if TYPE_CHECKING:
    from models.circuit import Circuit
    from models.lap import Lap
    from models.message import Message
    from models.pitstop import PitStop
    from models.position import Position
    from models.race_control import RaceControlMessage
    from models.result import Result
    from models.season import Season
    from models.telemetry import Telemetry
    from models.weather import Weather


class Session(Base):
    __tablename__ = "sessions"
    __table_args__ = (
        Index("ix_sessions_circuit_key", "circuit_key"),
        Index("ix_sessions_year_session_type", "year", "session_type"),
        Index("ix_sessions_date_start", "date_start"),
    )

    session_key: Mapped[int] = mapped_column(primary_key=True)
    meeting_key: Mapped[int | None] = mapped_column()
    circuit_key: Mapped[int | None] = mapped_column(ForeignKey("circuits.circuit_key"))
    year: Mapped[int | None] = mapped_column(ForeignKey("seasons.year"))
    session_type: Mapped[str | None] = mapped_column()
    session_name: Mapped[str | None] = mapped_column()
    date_start: Mapped[dt.datetime | None] = mapped_column()
    date_end: Mapped[dt.datetime | None] = mapped_column()
    is_cancelled: Mapped[bool] = mapped_column(default=False)

    circuit: Mapped[Circuit | None] = relationship(back_populates="sessions")
    season: Mapped[Season | None] = relationship(back_populates="sessions")
    results: Mapped[list[Result]] = relationship(back_populates="session")
    laps: Mapped[list[Lap]] = relationship(back_populates="session")
    pit_stops: Mapped[list[PitStop]] = relationship(back_populates="session")
    weather_samples: Mapped[list[Weather]] = relationship(back_populates="session")
    positions: Mapped[list[Position]] = relationship(back_populates="session")
    race_control_messages: Mapped[list[RaceControlMessage]] = relationship(back_populates="session")
    radio_messages: Mapped[list[Message]] = relationship(back_populates="session")
    telemetry_samples: Mapped[list[Telemetry]] = relationship(back_populates="session")
