from __future__ import annotations

from datetime import datetime
from decimal import Decimal

from pydantic import BaseModel
from pydantic import ConfigDict
from pydantic import EmailStr
from pydantic import Field

from src.models import AlertStatus
from src.models import Coin
from src.models import Direction


class RegisterIn(BaseModel):
    email: EmailStr
    password: str = Field(min_length=8, max_length=128)


class UserOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    email: EmailStr


class LoginIn(BaseModel):
    email: EmailStr
    password: str = Field(min_length=1, max_length=128)


class TokenOut(BaseModel):
    access_token: str
    token_type: str = "bearer"


class MePatch(BaseModel):
    link_code: str = Field(min_length=4, max_length=64)


class AlertIn(BaseModel):
    coin: Coin
    direction: Direction
    threshold: Decimal = Field(gt=0)


class AlertOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    coin: Coin
    direction: Direction
    threshold: Decimal
    status: AlertStatus
    created_at: datetime
    triggered_at: datetime | None
    triggered_price: Decimal | None


class CandleOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    time: datetime
    open: Decimal
    high: Decimal
    low: Decimal
    close: Decimal
