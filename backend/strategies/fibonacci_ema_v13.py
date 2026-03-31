from __future__ import annotations

from dataclasses import dataclass, field

import numpy as np
import pandas as pd


@dataclass(slots=True)
class SignalWindow:
    signal_day: pd.Timestamp
    signal_close: float
    eligible_day_count: int = 1
    consumed: bool = False


@dataclass(slots=True)
class PendingEntry:
    submitted_at: pd.Timestamp
    anchor_price: float


@dataclass(slots=True)
class SymbolState:
    last_seen_day: pd.Timestamp | None = None
    signal_windows: list[SignalWindow] = field(default_factory=list)
    pending_entry: PendingEntry | None = None
    pending_exit_at: pd.Timestamp | None = None
    active_anchor_price: float | None = None
    entry_day: pd.Timestamp | None = None


class FibonacciEmaV13Strategy:
    name = 'fibonacci_ema_v13'

    def __init__(self, buy_size: int = 100, take_profit: float = 0.1, stop_loss: float = 0.1):
        self.buy_size = buy_size
        self.take_profit = take_profit
        self.stop_loss = stop_loss
        self._states: dict[str, SymbolState] = {}

    def initialize(self, context: dict) -> None:
        self._states = {}

    def on_bar(self, context, bars):
        orders: list[dict] = []

        for symbol, bar in bars.items():
            state = self._states.setdefault(symbol, SymbolState())
            current_day = pd.Timestamp(bar.datetime).normalize()
            self._roll_day_if_needed(context, symbol, state, current_day)
            self._reconcile_pending_orders(context, symbol, state, pd.Timestamp(bar.datetime), current_day)

            sell_order = self._build_sell_order(context, symbol, bar, state, current_day)
            if sell_order is not None:
                orders.append(sell_order)

        if orders:
            return orders

        for symbol, bar in bars.items():
            state = self._states.setdefault(symbol, SymbolState())
            buy_order = self._build_buy_order(context, symbol, bar, state)
            if buy_order is not None:
                return buy_order

        return None

    def _roll_day_if_needed(self, context: dict, symbol: str, state: SymbolState, current_day: pd.Timestamp) -> None:
        if state.last_seen_day is None:
            state.last_seen_day = current_day
            self._register_previous_day_signal(context, symbol, state, current_day)
            return

        if current_day == state.last_seen_day:
            return

        for window in state.signal_windows:
            window.eligible_day_count += 1
        state.signal_windows = [window for window in state.signal_windows if window.eligible_day_count <= 3]
        state.last_seen_day = current_day
        self._register_previous_day_signal(context, symbol, state, current_day)

    def _register_previous_day_signal(self, context: dict, symbol: str, state: SymbolState, current_day: pd.Timestamp) -> None:
        minute_frame = context['data_portal'].get_history(symbol, end_datetime=current_day)
        if minute_frame.empty:
            return

        completed_minutes = minute_frame[minute_frame.index.normalize() < current_day]
        if completed_minutes.empty:
            return

        day_frame = self._aggregate_to_daily(completed_minutes)
        if day_frame.empty:
            return

        entry_signal = self._compute_entry_signal(day_frame)
        signal_day = day_frame.index[-1]
        if not bool(entry_signal.iloc[-1]):
            return
        if any(window.signal_day == signal_day for window in state.signal_windows):
            return

        state.signal_windows.insert(
            0,
            SignalWindow(
                signal_day=signal_day,
                signal_close=float(day_frame['close'].iloc[-1]),
            ),
        )

    def _reconcile_pending_orders(
        self,
        context: dict,
        symbol: str,
        state: SymbolState,
        timestamp: pd.Timestamp,
        current_day: pd.Timestamp,
    ) -> None:
        position = context['broker'].account.positions.get(symbol)
        has_position = position is not None and position.quantity > 0

        if state.pending_entry is not None and timestamp > state.pending_entry.submitted_at:
            if has_position:
                state.active_anchor_price = state.pending_entry.anchor_price
                state.entry_day = current_day
            state.pending_entry = None

        if state.pending_exit_at is not None and timestamp > state.pending_exit_at:
            if not has_position:
                state.active_anchor_price = None
                state.entry_day = None
            state.pending_exit_at = None

        if not has_position and state.pending_entry is None and state.pending_exit_at is None:
            state.active_anchor_price = None
            state.entry_day = None

    def _build_sell_order(
        self,
        context: dict,
        symbol: str,
        bar,
        state: SymbolState,
        current_day: pd.Timestamp,
    ) -> dict | None:
        if state.pending_exit_at is not None or state.active_anchor_price is None:
            return None

        position = context['broker'].account.positions.get(symbol)
        if position is None or position.quantity <= 0 or position.sellable_quantity <= 0:
            return None
        if state.entry_day is not None and current_day <= state.entry_day:
            return None

        current_price = float(bar.close)
        anchor_price = float(state.active_anchor_price)
        if current_price >= anchor_price * (1 + self.take_profit) or current_price <= anchor_price * (1 - self.stop_loss):
            state.pending_exit_at = pd.Timestamp(bar.datetime)
            return {
                'symbol': symbol,
                'type': 'SELL',
                'quantity': position.sellable_quantity,
                'price': current_price,
                'execution': 'next_bar_price',
            }
        return None

    def _build_buy_order(self, context: dict, symbol: str, bar, state: SymbolState) -> dict | None:
        if state.pending_entry is not None or state.pending_exit_at is not None:
            return None

        position = context['broker'].account.positions.get(symbol)
        if position is not None and position.quantity > 0:
            return None

        recent_history = context['data_portal'].get_history(symbol, end_datetime=bar.datetime, window=2)
        if len(recent_history) < 2:
            return None

        previous_close = float(recent_history['close'].iloc[-2])
        current_close = float(bar.close)

        for window in state.signal_windows:
            if window.consumed:
                continue
            if previous_close >= window.signal_close and current_close < window.signal_close * 0.98:
                window.consumed = True
                state.pending_entry = PendingEntry(
                    submitted_at=pd.Timestamp(bar.datetime),
                    anchor_price=window.signal_close,
                )
                return {
                    'symbol': symbol,
                    'type': 'BUY',
                    'quantity': self.buy_size,
                    'price': current_close,
                    'execution': 'next_bar_price',
                }
        return None

    def _compute_entry_signal(self, day_frame: pd.DataFrame) -> pd.Series:
        week_frame = self._aggregate_to_weekly(day_frame)
        week_cond = self._compute_week_condition(week_frame)
        week_cond = week_cond.reindex(day_frame.index, method='bfill').fillna(False)

        close = day_frame['close']
        ma89 = self._ma(close, 89)
        bias89 = (close - ma89) / ma89 * 100
        day_cond_1 = bias89 < -5

        dif = self._ema(close, 2)
        dea = self._ema(self._slope(close, 30) * 5 + close, 20)
        day_cond_2 = self._cross(dif, dea)

        day_cond = day_cond_1 & day_cond_2
        day_cond.iloc[:89] = False
        return week_cond & day_cond

    def _compute_week_condition(self, week_frame: pd.DataFrame) -> pd.Series:
        close = week_frame['close']
        ema13 = self._ema(close, 13)
        ema21 = self._ema(close, 21)
        ema34 = self._ema(close, 34)
        week_cond = (ema13 > ema21) & (ema21 > ema34)
        week_cond.iloc[:34] = False
        return week_cond.shift(1).fillna(False).astype(bool)

    @staticmethod
    def _aggregate_to_daily(minute_frame: pd.DataFrame) -> pd.DataFrame:
        grouped = minute_frame.groupby(minute_frame.index.normalize())
        return grouped.agg(
            {
                'open': 'first',
                'high': 'max',
                'low': 'min',
                'close': 'last',
                'volume': 'sum',
                'amount': 'sum',
            }
        )

    @staticmethod
    def _aggregate_to_weekly(day_frame: pd.DataFrame) -> pd.DataFrame:
        grouped = day_frame.groupby(day_frame.index.to_period('W-FRI'))
        week_frame = grouped.agg(
            {
                'open': 'first',
                'high': 'max',
                'low': 'min',
                'close': 'last',
                'volume': 'sum',
                'amount': 'sum',
            }
        )
        week_frame.index = pd.DatetimeIndex(grouped.apply(lambda frame: frame.index.max()).values)
        return week_frame

    @staticmethod
    def _ma(series: pd.Series, window: int) -> pd.Series:
        return series.rolling(window=window).mean()

    @staticmethod
    def _ema(series: pd.Series, window: int) -> pd.Series:
        return series.ewm(alpha=2 / (window + 1), adjust=False).mean()

    @staticmethod
    def _slope(series: pd.Series, window: int) -> pd.Series:
        x_axis = np.arange(window, dtype=float)
        return series.rolling(window).apply(lambda values: np.polyfit(x_axis, values, 1)[0], raw=True)

    @staticmethod
    def _cross(left: pd.Series, right: pd.Series) -> pd.Series:
        return (left > right) & (left.shift(1) <= right.shift(1))
