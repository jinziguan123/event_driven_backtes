from __future__ import annotations

import numpy as np
import pandas as pd


def _to_series(value) -> pd.Series:
    if isinstance(value, pd.Series):
        return value
    if np.isscalar(value):
        return pd.Series([value], dtype=float)
    return pd.Series(value)


def REF(series, periods: int = 1) -> pd.Series:
    s = _to_series(series)
    return s.shift(int(periods))


def MA(series, periods: int) -> pd.Series:
    s = _to_series(series).astype(float)
    window = max(1, int(periods))
    return s.rolling(window=window, min_periods=window).mean()


def EMA(series, periods: int) -> pd.Series:
    s = _to_series(series).astype(float)
    span = max(1, int(periods))
    return s.ewm(span=span, adjust=False).mean()


def SMA(series, periods: int, weight: int = 1) -> pd.Series:
    values = _to_series(series).astype(float)
    n = max(1, int(periods))
    m = max(1, int(weight))
    result = pd.Series(index=values.index, dtype=float)
    if values.empty:
        return result

    first = values.iloc[0]
    result.iloc[0] = first
    for idx in range(1, len(values)):
        prev = result.iloc[idx - 1]
        current = values.iloc[idx]
        result.iloc[idx] = (m * current + (n - m) * prev) / n
    return result


def HHV(series, periods: int) -> pd.Series:
    s = _to_series(series).astype(float)
    n = int(periods)
    if n <= 0:
        return s.expanding(min_periods=1).max()
    return s.rolling(window=n, min_periods=1).max()


def LLV(series, periods: int) -> pd.Series:
    s = _to_series(series).astype(float)
    n = int(periods)
    if n <= 0:
        return s.expanding(min_periods=1).min()
    return s.rolling(window=n, min_periods=1).min()


def COUNT(condition, periods: int) -> pd.Series:
    cond = _to_series(condition).astype(bool).astype(int)
    n = int(periods)
    if n <= 0:
        return cond.cumsum()
    return cond.rolling(window=n, min_periods=1).sum()


def BARSLAST(condition) -> pd.Series:
    cond = _to_series(condition).astype(bool)
    result = pd.Series(index=cond.index, dtype=float)
    last_true = -1
    for idx, flag in enumerate(cond.tolist()):
        if flag:
            result.iloc[idx] = 0
            last_true = idx
        elif last_true < 0:
            result.iloc[idx] = np.nan
        else:
            result.iloc[idx] = idx - last_true
    return result


def CROSS(a, b) -> pd.Series:
    left = _to_series(a).astype(float)
    right = _to_series(b).astype(float)
    left, right = left.align(right, join='outer')
    current = left > right
    previous = left.shift(1) <= right.shift(1)
    return (current & previous).fillna(False)
