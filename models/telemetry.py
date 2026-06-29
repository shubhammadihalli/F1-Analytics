"""Car telemetry samples (speed/throttle/brake/RPM/gear/DRS) within a session.

By far the highest-volume table in this schema (~3.7 Hz per car for the
whole session) - uses a BigInteger surrogate key, unlike the other
surrogate-key tables, since row counts here can run into the tens of
millions across a season.
"""

from __future__ import annotations

import datetime as dt
from typing import TYPE_CHECKING

from sqlalchemy import BigInteger, CheckConstraint, ForeignKey, Index, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from database.base import Base

if TYPE_CHECKING:
    from models.driver import Driver
    from models.session import Session


class Telemetry(Base):
    __tablename__ = "telemetry"
    __table_args__ = (
        UniqueConstraint(
            "session_key", "driver_number", "date", name="uq_telemetry_session_driver_date"
        ),
        Index("ix_telemetry_session_driver", "session_key", "driver_number"),
        Index("ix_telemetry_date", "date"),
        # Not clean 0-100 percentages: OpenF1's raw sensor values for
        # throttle/brake are almost binary (0/100) but occasionally overshoot
        # past 100 (observed up to 104), so only non-negative floors are
        # enforced rather than an upper bound.
        CheckConstraint("speed IS NULL OR speed >= 0", name="ck_telemetry_speed_non_negative"),
        CheckConstraint("throttle IS NULL OR throttle >= 0", name="ck_telemetry_throttle_non_negative"),
        CheckConstraint("brake IS NULL OR brake >= 0", name="ck_telemetry_brake_non_negative"),
    )

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    session_key: Mapped[int] = mapped_column(ForeignKey("sessions.session_key"))
    driver_number: Mapped[int] = mapped_column(ForeignKey("drivers.driver_number"))
    date: Mapped[dt.datetime] = mapped_column()
    speed: Mapped[int | None] = mapped_column()
    throttle: Mapped[int | None] = mapped_column()
    brake: Mapped[int | None] = mapped_column()
    rpm: Mapped[int | None] = mapped_column()
    n_gear: Mapped[int | None] = mapped_column()
    drs: Mapped[int | None] = mapped_column()

    session: Mapped[Session] = relationship(back_populates="telemetry_samples")
    driver: Mapped[Driver] = relationship(back_populates="telemetry_samples")
