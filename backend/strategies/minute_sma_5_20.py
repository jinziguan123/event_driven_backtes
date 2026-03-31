from __future__ import annotations

import pandas as pd


class MinuteSma520Strategy:
    name = 'minute_sma_5_20'

    def __init__(self, short_window: int = 5, long_window: int = 20, lot_size: int = 100):
        self.short_window = short_window
        self.long_window = long_window
        self.lot_size = lot_size

    def _load_close_history(self, context: dict, symbol: str) -> pd.Series:
        history = context['data_portal'].get_history(symbol, end_datetime=context['timestamp'], window=self.long_window + 1)
        if history.empty or 'close' not in history.columns:
            return pd.Series(dtype=float)
        return history['close']

    def _calc_cross(self, closes: pd.Series) -> tuple[bool, bool]:
        if len(closes) < self.long_window:
            return False, False
        fast = closes.rolling(self.short_window).mean()
        slow = closes.rolling(self.long_window).mean()
        if len(fast) < 2 or pd.isna(fast.iloc[-2]) or pd.isna(slow.iloc[-2]) or pd.isna(fast.iloc[-1]) or pd.isna(slow.iloc[-1]):
            return False, False
        golden_cross = fast.iloc[-2] <= slow.iloc[-2] and fast.iloc[-1] > slow.iloc[-1]
        death_cross = fast.iloc[-2] >= slow.iloc[-2] and fast.iloc[-1] < slow.iloc[-1]
        return golden_cross, death_cross

    def _calculate_full_position_quantity(self, context: dict, price: float) -> int:
        if price <= 0:
            return 0
        available_cash = context['broker'].account.state.available_cash
        commission = context['config'].commission
        lot_cost = price * self.lot_size * (1 + commission)
        if lot_cost <= 0:
            return 0
        lots = int(available_cash // lot_cost)
        return lots * self.lot_size

    def on_bar(self, context, bars):
        broker = context['broker']

        for symbol in bars:
            position = broker.account.positions.get(symbol)
            if position is None or position.quantity <= 0 or position.sellable_quantity <= 0:
                continue
            closes = self._load_close_history(context, symbol)
            _, death_cross = self._calc_cross(closes)
            if death_cross:
                return {'symbol': symbol, 'type': 'SELL', 'quantity': position.sellable_quantity}

        if any(position.quantity > 0 for position in broker.account.positions.values()):
            return None

        for symbol, bar in bars.items():
            closes = self._load_close_history(context, symbol)
            golden_cross, _ = self._calc_cross(closes)
            if not golden_cross:
                continue
            quantity = self._calculate_full_position_quantity(context, bar.close)
            if quantity < self.lot_size:
                return None
            return {'symbol': symbol, 'type': 'BUY', 'quantity': quantity}

        return None
