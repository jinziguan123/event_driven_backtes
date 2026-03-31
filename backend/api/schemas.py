from __future__ import annotations

from pydantic import BaseModel, Field, model_validator


class BacktestCreateRequest(BaseModel):
    symbols: list[str] = Field(default_factory=list)
    pool_id: str | None = None
    initial_cash: float = 1_000_000
    name: str = '未命名回测'
    strategy_name: str = '未指定策略'
    strategy_path: str | None = None
    strategy_type: str = 'class'
    start_datetime: str | None = None
    end_datetime: str | None = None
    bar_frequency: str = '1m'
    max_positions: int = 5
    slippage: float = 0.0
    commission: float = 0.0003
    stamp_duty: float = 0.001
    adjustment: str = 'qfq'
    match_mode: str = 'next_open'
    benchmark: str = '000300.SH'

    @model_validator(mode='after')
    def validate_symbols_or_pool(self):
        if self.symbols or self.pool_id:
            return self
        raise ValueError('symbols 和 pool_id 至少提供一个')


class BacktestCreateResponse(BaseModel):
    run_id: str
    status: str


class BacktestCancelResponse(BaseModel):
    run_id: str
    status: str
    accepted: bool
    message: str = ''


class BacktestDeleteResponse(BaseModel):
    run_id: str
    deleted: bool
    message: str | None = None


class StrategySummary(BaseModel):
    name: str
    path: str


class StockPoolCreateRequest(BaseModel):
    name: str = Field(min_length=1)
    description: str = ''
    symbols: list[str] = Field(default_factory=list)


class StockPoolUpdateRequest(BaseModel):
    name: str = Field(min_length=1)
    description: str = ''
    symbols: list[str] = Field(default_factory=list)


class StockPoolResponse(BaseModel):
    pool_id: str
    name: str
    description: str
    symbols: list[str]
    symbol_count: int
    created_at: str
    updated_at: str


class StockPoolSummary(BaseModel):
    pool_id: str
    name: str
    description: str
    symbol_count: int
    created_at: str
    updated_at: str


class StockSymbolOption(BaseModel):
    symbol: str


class StockSymbolPageResponse(BaseModel):
    items: list[StockSymbolOption]
    total: int
    page: int
    page_size: int


class BacktestProfileResponse(BaseModel):
    run_id: str
    profile: dict
