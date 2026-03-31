from __future__ import annotations

from collections.abc import Iterable
from typing import Final
import warnings

import pandas as pd

from .clickhouse_loader import ClickHouseMinuteBarLoader

DEFAULT_FIELDS: Final[list[str]] = ['open', 'high', 'low', 'close', 'volume', 'amount']
_DEFAULT_LOADER: ClickHouseMinuteBarLoader | None = None
_QFQ_WARNING_EMITTED = False


def _get_loader(loader: ClickHouseMinuteBarLoader | None = None) -> ClickHouseMinuteBarLoader:
    if loader is not None:
        return loader
    global _DEFAULT_LOADER
    if _DEFAULT_LOADER is None:
        _DEFAULT_LOADER = ClickHouseMinuteBarLoader()
    return _DEFAULT_LOADER


def _apply_adjustment(symbol: str, df: pd.DataFrame, adjustment: str) -> pd.DataFrame:
    del symbol
    if df.empty or adjustment == 'none':
        return df

    if adjustment == 'qfq':
        global _QFQ_WARNING_EMITTED
        if not _QFQ_WARNING_EMITTED:
            warnings.warn(
                'event_driven_backtest 暂未接入前复权因子，qfq 当前回退为原始价格数据',
                RuntimeWarning,
                stacklevel=2,
            )
            _QFQ_WARNING_EMITTED = True
        return df

    if adjustment == 'hfq':
        raise NotImplementedError('首版暂未实现后复权')

    raise ValueError(f'不支持的复权方式: {adjustment}')


def load_symbol_minutes(
    symbol: str,
    start_datetime: str | None = None,
    end_datetime: str | None = None,
    fields: list[str] | None = None,
    adjustment: str = 'qfq',
    loader: ClickHouseMinuteBarLoader | None = None,
) -> pd.DataFrame:
    frame = _get_loader(loader).load_symbol_minutes(
        symbol=symbol,
        start_datetime=start_datetime,
        end_datetime=end_datetime,
        fields=fields or DEFAULT_FIELDS,
    )
    return _apply_adjustment(symbol, frame, adjustment)


def load_symbol_map(
    symbols: Iterable[str],
    start_datetime: str | None = None,
    end_datetime: str | None = None,
    fields: list[str] | None = None,
    adjustment: str = 'qfq',
    loader: ClickHouseMinuteBarLoader | None = None,
) -> dict[str, pd.DataFrame]:
    active_loader = _get_loader(loader)
    return {
        symbol: load_symbol_minutes(
            symbol=symbol,
            start_datetime=start_datetime,
            end_datetime=end_datetime,
            fields=fields,
            adjustment=adjustment,
            loader=active_loader,
        )
        for symbol in symbols
    }
