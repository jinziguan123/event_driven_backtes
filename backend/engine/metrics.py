from __future__ import annotations

import math
from collections.abc import Iterable

import pandas as pd


def _to_drawdown_series(equity: pd.Series) -> pd.Series:
    if equity.empty:
        return pd.Series(dtype=float)
    equity = equity.astype(float)
    rolling_peak = equity.cummax()
    return (equity / rolling_peak) - 1.0


def compute_max_drawdown_window(equity: pd.Series) -> dict[str, str | float | None]:
    if equity.empty:
        return {
            'peak_time': None,
            'trough_time': None,
            'recovery_time': None,
            'max_drawdown': 0.0,
        }

    equity = equity.astype(float)
    rolling_peak = equity.cummax()
    drawdown = _to_drawdown_series(equity)
    trough_time = drawdown.idxmin()
    max_drawdown = abs(float(drawdown.loc[trough_time]))

    history = equity.loc[:trough_time]
    peak_time = history.idxmax()
    peak_value = float(history.loc[peak_time])

    recovery_slice = equity.loc[trough_time:]
    recovery_candidates = recovery_slice[recovery_slice >= peak_value]
    recovery_time = None
    if not recovery_candidates.empty:
        recovery_time = recovery_candidates.index[0]

    def _fmt(ts):
        if ts is None:
            return None
        return ts.strftime('%Y-%m-%d %H:%M:%S') if hasattr(ts, 'strftime') else str(ts)

    return {
        'peak_time': _fmt(peak_time),
        'trough_time': _fmt(trough_time),
        'recovery_time': _fmt(recovery_time) if recovery_time is not None else None,
        'max_drawdown': max_drawdown,
    }


def build_benchmark_curve(
    benchmark_price: pd.Series,
    equity_index: Iterable[pd.Timestamp] | pd.DatetimeIndex,
    initial_cash: float,
) -> pd.DataFrame:
    if benchmark_price.empty:
        return pd.DataFrame(columns=['benchmark_price', 'benchmark_equity', 'benchmark_return'])

    benchmark_price = benchmark_price.astype(float).sort_index()
    target_index = pd.DatetimeIndex(equity_index)
    aligned_price = benchmark_price.reindex(target_index, method='ffill')
    aligned_price = aligned_price.bfill()
    aligned_price = aligned_price.dropna()
    if aligned_price.empty:
        return pd.DataFrame(columns=['benchmark_price', 'benchmark_equity', 'benchmark_return'])

    first_price = float(aligned_price.iloc[0])
    benchmark_equity = (aligned_price / first_price) * float(initial_cash)
    benchmark_return = (aligned_price / first_price) - 1.0
    frame = pd.DataFrame(
        {
            'benchmark_price': aligned_price,
            'benchmark_equity': benchmark_equity,
            'benchmark_return': benchmark_return,
        },
        index=aligned_price.index,
    )
    frame.index.name = 'timestamp'
    return frame


def build_drawdown_curve(
    strategy_equity: pd.Series,
    benchmark_equity: pd.Series | None = None,
) -> pd.DataFrame:
    strategy_curve = _to_drawdown_series(strategy_equity)
    frame = pd.DataFrame({'strategy_drawdown': strategy_curve})
    if benchmark_equity is not None and not benchmark_equity.empty:
        benchmark_curve = _to_drawdown_series(benchmark_equity.reindex(strategy_curve.index, method='ffill').bfill())
        frame['benchmark_drawdown'] = benchmark_curve
    frame.index.name = 'timestamp'
    return frame


def compute_core_metrics(equity: pd.Series, trades: pd.DataFrame | None = None) -> dict[str, float | int]:
    if equity.empty:
        return {
            'total_return': 0.0,
            'annual_return': 0.0,
            'sharpe_ratio': 0.0,
            'max_drawdown': 0.0,
            'win_rate': 0.0,
            'trade_count': 0,
            'max_drawdown_window': {
                'peak_time': None,
                'trough_time': None,
                'recovery_time': None,
                'max_drawdown': 0.0,
            },
        }

    equity = equity.astype(float)
    returns = equity.pct_change().dropna()
    total_return = float((equity.iloc[-1] / equity.iloc[0]) - 1)
    annual_return = float((1 + total_return) ** (252 / max(len(equity) - 1, 1)) - 1) if len(equity) > 1 else total_return
    sharpe_ratio = 0.0
    if not returns.empty and returns.std() not in (0, 0.0):
        sharpe_ratio = float((returns.mean() / returns.std()) * math.sqrt(252))

    drawdown = _to_drawdown_series(equity)
    max_drawdown = abs(float(drawdown.min())) if not drawdown.empty else 0.0

    trade_count = 0
    win_rate = 0.0
    if trades is not None and not trades.empty and 'pnl' in trades.columns:
        trade_count = int(len(trades))
        win_rate = float((trades['pnl'] > 0).sum() / trade_count) if trade_count else 0.0

    return {
        'total_return': total_return,
        'annual_return': annual_return,
        'sharpe_ratio': sharpe_ratio,
        'max_drawdown': max_drawdown,
        'win_rate': win_rate,
        'trade_count': trade_count,
        'max_drawdown_window': compute_max_drawdown_window(equity),
    }
