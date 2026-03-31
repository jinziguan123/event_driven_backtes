from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Iterable

import pandas as pd

from .aggregator import aggregate_symbol_map
from .raw_loader import load_symbol_map


@dataclass(slots=True)
class DataPortal:
    bars_by_symbol: dict[str, pd.DataFrame]

    @classmethod
    def from_loader(
        cls,
        symbols: Iterable[str],
        start_datetime: str | None = None,
        end_datetime: str | None = None,
        adjustment: str = 'qfq',
        bar_frequency: str = '1m',
    ) -> 'DataPortal':
        data = load_symbol_map(
            symbols=symbols,
            start_datetime=start_datetime,
            end_datetime=end_datetime,
            adjustment=adjustment,
        )
        if bar_frequency != '1m':
            data = aggregate_symbol_map(data, bar_frequency)
        return cls(bars_by_symbol=data)

    def symbols(self) -> list[str]:
        return list(self.bars_by_symbol.keys())

    def get_history(
        self,
        symbol: str,
        end_datetime: datetime | str | None = None,
        window: int | None = None,
    ) -> pd.DataFrame:
        frame = self.bars_by_symbol.get(symbol, pd.DataFrame()).copy()
        if frame.empty:
            return frame
        if end_datetime is not None:
            frame = frame.loc[:pd.Timestamp(end_datetime)]
        if window is not None:
            frame = frame.tail(window)
        return frame

    def get_bar(self, symbol: str, timestamp: datetime | str) -> pd.Series | None:
        frame = self.bars_by_symbol.get(symbol)
        if frame is None or frame.empty:
            return None
        ts = pd.Timestamp(timestamp)
        if ts not in frame.index:
            return None
        return frame.loc[ts]

    def slice(
        self,
        symbol: str,
        start_datetime: datetime | str | None = None,
        end_datetime: datetime | str | None = None,
    ) -> pd.DataFrame:
        frame = self.bars_by_symbol.get(symbol, pd.DataFrame()).copy()
        if frame.empty:
            return frame
        if start_datetime is not None:
            frame = frame.loc[pd.Timestamp(start_datetime):]
        if end_datetime is not None:
            frame = frame.loc[:pd.Timestamp(end_datetime)]
        return frame
