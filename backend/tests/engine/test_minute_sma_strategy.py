from datetime import datetime, timedelta
from pathlib import Path
import unittest

import pandas as pd

from event_driven_backtest.backend.core.config import BacktestConfig
from event_driven_backtest.backend.core.models import MarketBar, Position
from event_driven_backtest.backend.data.portal import DataPortal
from event_driven_backtest.backend.engine.broker import Broker
from event_driven_backtest.backend.strategy_sdk.loader import load_strategy


STRATEGY_PATH = Path('event_driven_backtest/backend/strategies/minute_sma_5_20.py')
SYMBOL = '000001.SZ'


class MinuteSmaStrategyTest(unittest.TestCase):
    def _build_frame(self, closes: list[float]) -> pd.DataFrame:
        start = datetime(2026, 1, 2, 9, 31)
        index = [start + timedelta(minutes=offset) for offset in range(len(closes))]
        return pd.DataFrame(
            {
                'open': closes,
                'high': closes,
                'low': closes,
                'close': closes,
                'volume': [1000] * len(closes),
                'amount': [price * 1000 for price in closes],
            },
            index=index,
        )

    def _build_context(self, frame: pd.DataFrame, initial_cash: float = 100000.0):
        portal = DataPortal({SYMBOL: frame})
        config = BacktestConfig(symbols=[SYMBOL], initial_cash=initial_cash, match_mode='close')
        broker = Broker(config)
        timestamp = frame.index[-1]
        row = frame.iloc[-1]
        bars = {
            SYMBOL: MarketBar(
                symbol=SYMBOL,
                datetime=timestamp.to_pydatetime(),
                open=float(row['open']),
                high=float(row['high']),
                low=float(row['low']),
                close=float(row['close']),
                volume=float(row['volume']),
                amount=float(row['amount']),
            )
        }
        context = {
            'config': config,
            'broker': broker,
            'data_portal': portal,
            'timestamp': timestamp,
            'logs': [],
        }
        return context, bars

    def test_strategy_buys_when_fast_sma_crosses_above_slow_sma(self):
        closes = [10.0] * 20 + [8.0, 8.0, 8.0, 8.0, 20.0]
        frame = self._build_frame(closes)
        strategy = load_strategy(STRATEGY_PATH)
        context, bars = self._build_context(frame)

        result = strategy.on_bar(context, bars)

        self.assertIsNotNone(result)
        self.assertEqual(result['symbol'], SYMBOL)
        self.assertEqual(result['type'], 'BUY')
        self.assertGreater(result['quantity'], 0)
        self.assertEqual(result['quantity'] % 100, 0)

    def test_strategy_sells_when_fast_sma_crosses_below_slow_sma(self):
        closes = [10.0] * 20 + [12.0, 12.0, 12.0, 7.0, 7.0, 7.0]
        frame = self._build_frame(closes)
        strategy = load_strategy(STRATEGY_PATH)
        context, bars = self._build_context(frame)
        context['broker'].account.positions[SYMBOL] = Position(
            symbol=SYMBOL,
            quantity=1000,
            sellable_quantity=1000,
            avg_cost=10.0,
        )

        result = strategy.on_bar(context, bars)

        self.assertIsNotNone(result)
        self.assertEqual(result['symbol'], SYMBOL)
        self.assertEqual(result['type'], 'SELL')
        self.assertEqual(result['quantity'], 1000)


if __name__ == '__main__':
    unittest.main()
