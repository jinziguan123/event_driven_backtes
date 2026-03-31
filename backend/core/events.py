from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Any


class EventType(str, Enum):
    BAR_OPEN = 'BAR_OPEN'
    BAR_CLOSE = 'BAR_CLOSE'
    SIGNAL = 'SIGNAL'
    ORDER_SUBMITTED = 'ORDER_SUBMITTED'
    ORDER_FILLED = 'ORDER_FILLED'
    ORDER_REJECTED = 'ORDER_REJECTED'
    AFTER_TRADING = 'AFTER_TRADING'
    BACKTEST_FINISHED = 'BACKTEST_FINISHED'


@dataclass(slots=True)
class Event:
    type: EventType
    timestamp: datetime
    payload: dict[str, Any] = field(default_factory=dict)
