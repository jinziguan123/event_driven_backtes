from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from typing import Any


VALID_MATCH_MODES = {'close', 'next_open', 'limit'}
VALID_ADJUSTMENTS = {'none', 'qfq', 'hfq'}
VALID_STRATEGY_TYPES = {'class', 'script'}


@dataclass(slots=True)
class BacktestConfig:
    symbols: list[str]
    initial_cash: float = 1_000_000
    max_positions: int = 5
    slippage: float = 0.0
    commission: float = 0.0003
    stamp_duty: float = 0.001
    adjustment: str = 'qfq'
    match_mode: str = 'next_open'
    enable_t1: bool = True
    data_frequency: str = '1m'
    bar_frequency: str = '1m'
    strategy_type: str = 'class'
    strategy_path: str | None = None
    start_datetime: datetime | None = None
    end_datetime: datetime | None = None
    benchmark: str | None = '000300.SH'
    metadata: dict[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        if not self.symbols:
            raise ValueError('symbols 不能为空')
        if self.initial_cash <= 0:
            raise ValueError('initial_cash 必须大于 0')
        if self.max_positions < 1:
            raise ValueError('max_positions 必须大于等于 1')
        if self.match_mode not in VALID_MATCH_MODES:
            raise ValueError(f'match_mode 仅支持: {sorted(VALID_MATCH_MODES)}')
        if self.adjustment not in VALID_ADJUSTMENTS:
            raise ValueError(f'adjustment 仅支持: {sorted(VALID_ADJUSTMENTS)}')
        if self.strategy_type not in VALID_STRATEGY_TYPES:
            raise ValueError(f'strategy_type 仅支持: {sorted(VALID_STRATEGY_TYPES)}')
        if self.start_datetime and self.end_datetime and self.start_datetime > self.end_datetime:
            raise ValueError('start_datetime 不能晚于 end_datetime')
