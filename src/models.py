from __future__ import annotations

import enum
from datetime import datetime
from decimal import Decimal

from sqlalchemy import BigInteger
from sqlalchemy import DateTime
from sqlalchemy import Enum
from sqlalchemy import ForeignKey
from sqlalchemy import Index
from sqlalchemy import Numeric
from sqlalchemy import String
from sqlalchemy import func
from sqlalchemy import text
from sqlalchemy.orm import Mapped
from sqlalchemy.orm import mapped_column
from sqlalchemy.orm import relationship

from src.db import Base


class Coin(enum.StrEnum):
    BTC = "BTC"
    ETH = "ETH"
    SOL = "SOL"
    BNB = "BNB"
    XRP = "XRP"


class Direction(enum.StrEnum):
    above = "above"
    below = "below"


class AlertStatus(enum.StrEnum):
    active = "active"
    triggered = "triggered"
    cancelled = "cancelled"


class User(Base):
    __tablename__ = "users"

    id: Mapped[int] = mapped_column(primary_key=True)
    email: Mapped[str] = mapped_column(String(255), unique=True)
    password_hash: Mapped[str] = mapped_column(String(255))
    telegram_chat_id: Mapped[int | None] = mapped_column(BigInteger, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )

    alerts: Mapped[list[Alert]] = relationship(back_populates="user")


class Alert(Base):
    __tablename__ = "alerts"

    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"))
    coin: Mapped[Coin] = mapped_column(Enum(Coin, name="coin"))
    direction: Mapped[Direction] = mapped_column(Enum(Direction, name="direction"))
    threshold: Mapped[Decimal] = mapped_column(Numeric(18, 8))
    status: Mapped[AlertStatus] = mapped_column(
        Enum(AlertStatus, name="alert_status"), default=AlertStatus.active
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
    triggered_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    triggered_price: Mapped[Decimal | None] = mapped_column(
        Numeric(18, 8), nullable=True
    )

    user: Mapped[User] = relationship(back_populates="alerts")

    __table_args__ = (
        Index(
            "ix_alerts_active_by_coin",
            "coin",
            postgresql_where=text("status = 'active'"),
        ),
        Index(
            "ix_alerts_active_by_user",
            "user_id",
            postgresql_where=text("status = 'active'"),
        ),
    )


class Candle1m(Base):
    __tablename__ = "candles_1m"

    coin: Mapped[Coin] = mapped_column(Enum(Coin, name="coin"), primary_key=True)
    open_time: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), primary_key=True
    )
    open: Mapped[Decimal] = mapped_column(Numeric(18, 8))
    high: Mapped[Decimal] = mapped_column(Numeric(18, 8))
    low: Mapped[Decimal] = mapped_column(Numeric(18, 8))
    close: Mapped[Decimal] = mapped_column(Numeric(18, 8))
    volume: Mapped[Decimal] = mapped_column(Numeric(28, 8))
