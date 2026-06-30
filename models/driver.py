"""Driver model.

Car numbers are reused across F1 history, but OpenF1 only covers 2023
onward, where each active number maps to a single driver - safe as a PK.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from sqlalchemy import ForeignKey, Index
from sqlalchemy.orm import Mapped, mapped_column, relationship

from database.base import Base

if TYPE_CHECKING:
    from models.constructor import Constructor
    from models.driver_standing import DriverStanding
    from models.lap import Lap
    from models.message import Message
    from models.pitstop import PitStop
    from models.position import Position
    from models.race_control import RaceControlMessage
    from models.result import Result
    from models.starting_grid import StartingGridPosition
    from models.stint import Stint
    from models.telemetry import Telemetry


class Driver(Base):
    __tablename__ = "drivers"
    __table_args__ = (Index("ix_drivers_team_name", "team_name"),)

    driver_number: Mapped[int] = mapped_column(primary_key=True)
    full_name: Mapped[str | None] = mapped_column()
    broadcast_name: Mapped[str | None] = mapped_column()
    name_acronym: Mapped[str | None] = mapped_column()
    first_name: Mapped[str | None] = mapped_column()
    last_name: Mapped[str | None] = mapped_column()
    country_code: Mapped[str | None] = mapped_column()
    headshot_url: Mapped[str | None] = mapped_column()
    team_name: Mapped[str | None] = mapped_column(ForeignKey("constructors.team_name"))

    constructor: Mapped[Constructor | None] = relationship(back_populates="drivers")
    results: Mapped[list[Result]] = relationship(back_populates="driver")
    laps: Mapped[list[Lap]] = relationship(back_populates="driver")
    pit_stops: Mapped[list[PitStop]] = relationship(back_populates="driver")
    positions: Mapped[list[Position]] = relationship(back_populates="driver")
    standings: Mapped[list[DriverStanding]] = relationship(back_populates="driver")
    race_control_messages: Mapped[list[RaceControlMessage]] = relationship(back_populates="driver")
    radio_messages: Mapped[list[Message]] = relationship(back_populates="driver")
    telemetry_samples: Mapped[list[Telemetry]] = relationship(back_populates="driver")
    stints: Mapped[list[Stint]] = relationship(back_populates="driver")
    starting_grid_positions: Mapped[list[StartingGridPosition]] = relationship(back_populates="driver")
