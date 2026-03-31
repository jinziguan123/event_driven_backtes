from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum


class OrderSide(str, Enum):
    BUY = 'BUY'
    SELL = 'SELL'


class OrderStatus(str, Enum):
    PENDING = 'PENDING'
    FILLED = 'FILLED'
    REJECTED = 'REJECTED'
    CANCELLED = 'CANCELLED'


@dataclass(slots=True)
class MarketBar:
    symbol: str
    datetime: datetime
    open: float
    high: float
    low: float
    close: float
    volume: float
    amount: float


@dataclass(slots=True)
class Order:
    symbol: str
    side: OrderSide
    quantity: int
    submitted_at: datetime
    price: float | None = None
    status: OrderStatus = OrderStatus.PENDING
    filled_at: datetime | None = None
    filled_price: float | None = None
    reject_reason: str | None = None


@dataclass(slots=True)
class Trade:
    symbol: str
    side: OrderSide
    quantity: int
    price: float
    timestamp: datetime
    commission: float = 0.0
    stamp_duty: float = 0.0
    pnl: float = 0.0


@dataclass(slots=True)
class Position:
    symbol: str
    quantity: int = 0
    sellable_quantity: int = 0
    avg_cost: float = 0.0
    market_value: float = 0.0
    unrealized_pnl: float = 0.0
    last_updated: datetime | None = None


@dataclass(slots=True)
class AccountState:
    cash: float
    frozen_cash: float = 0.0
    total_equity: float = 0.0
    market_value: float = 0.0
    cumulative_commission: float = 0.0
    cumulative_stamp_duty: float = 0.0

    @property
    def available_cash(self) -> float:
        return max(self.cash - self.frozen_cash, 0.0)


@dataclass(slots=True)
class PortfolioSnapshot:
    timestamp: datetime
    cash: float
    market_value: float
    total_equity: float
    position_ratio: float
    drawdown: float = 0.0
    daily_pnl: float = 0.0
    metadata: dict[str, float | int | str] = field(default_factory=dict)
