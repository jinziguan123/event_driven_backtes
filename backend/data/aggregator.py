from __future__ import annotations

from collections.abc import Mapping

import pandas as pd


AGGREGATION_RULES: dict[str, str] = {
    'open': 'first',
    'high': 'max',
    'low': 'min',
    'close': 'last',
    'volume': 'sum',
    'amount': 'sum',
}


def normalize_frequency(frequency: str) -> str:
    normalized = frequency.strip().lower()
    mapping = {
        '1m': '1min',
        '5m': '5min',
        '15m': '15min',
        '30m': '30min',
        '60m': '60min',
        '1h': '60min',
        '1d': '1D',
        '1w': '1W-FRI',
    }
    return mapping.get(normalized, frequency)


def aggregate_bars(df: pd.DataFrame, frequency: str) -> pd.DataFrame:
    if df.empty:
        return df.copy()

    frame = df.copy()
    if not isinstance(frame.index, pd.DatetimeIndex):
        frame.index = pd.to_datetime(frame.index)

    agg_spec = {
        column: AGGREGATION_RULES[column]
        for column in frame.columns
        if column in AGGREGATION_RULES
    }
    if not agg_spec:
        raise ValueError('未找到可聚合的 OHLCV 字段')

    aggregated = frame.resample(
        normalize_frequency(frequency),
        label='right',
        closed='right',
    ).agg(agg_spec)

    required_cols = [column for column in ('open', 'close') if column in aggregated.columns]
    if required_cols:
        aggregated = aggregated.dropna(subset=required_cols)
    else:
        aggregated = aggregated.dropna(how='all')

    aggregated.index.name = frame.index.name or 'datetime'
    return aggregated


def aggregate_symbol_map(symbol_map: Mapping[str, pd.DataFrame], frequency: str) -> dict[str, pd.DataFrame]:
    return {
        symbol: aggregate_bars(df, frequency)
        for symbol, df in symbol_map.items()
    }
