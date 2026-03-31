from datetime import datetime
from pathlib import Path
import unittest

import numpy as np
import pandas as pd

from event_driven_backtest.backend.core.config import BacktestConfig
from event_driven_backtest.backend.data.portal import DataPortal
from event_driven_backtest.backend.engine.runner import BacktestRunner
from event_driven_backtest.backend.strategy_sdk.loader import load_strategy


STRATEGY_PATH = Path('event_driven_backtest/backend/strategies/fibonacci_ema_v13.py')
SYMBOL = '000001.SZ'


class FibonacciEmaV13StrategyTest(unittest.TestCase):
    def _build_frame(self) -> pd.DataFrame:
        rng = np.random.default_rng(1)
        days = pd.bdate_range('2024-01-01', periods=220)
        base = np.concatenate(
            [
                np.linspace(50, 150, 170),
                np.linspace(150, 88, 25),
                np.linspace(88, 100, 10),
                np.linspace(100, 110, 15),
            ]
        )
        noise = rng.normal(0, 1.2, size=len(base))
        day_closes = pd.Series(base + noise, index=days)
        pivot = 190
        day_closes.iloc[pivot - 3 : pivot + 7] = [106, 101, 96, 92, 90, 91, 93, 97, 99, 101]

        rows: list[dict] = []
        index: list[pd.Timestamp] = []
        for day, day_close in day_closes.items():
            minute_closes = np.array(
                [
                    day_close * 1.002,
                    day_close * 0.998,
                    day_close * 1.001,
                    day_close,
                ],
                dtype=float,
            )
            if day == pd.Timestamp('2024-10-08'):
                minute_closes = np.array([97.5, 94.0, 95.0, day_close], dtype=float)
            if day == pd.Timestamp('2024-10-09'):
                minute_closes = np.array([100.0, 107.0, 106.0, day_close], dtype=float)

            minute_times = [
                day + pd.Timedelta(hours=9, minutes=31),
                day + pd.Timedelta(hours=10, minutes=0),
                day + pd.Timedelta(hours=14, minutes=0),
                day + pd.Timedelta(hours=14, minutes=59),
            ]
            previous_close = float(day_close)
            for ts, close in zip(minute_times, minute_closes):
                open_price = previous_close
                rows.append(
                    {
                        'open': open_price,
                        'high': max(open_price, close) + 0.1,
                        'low': min(open_price, close) - 0.1,
                        'close': float(close),
                        'volume': 1000.0,
                        'amount': float(close) * 1000.0,
                    }
                )
                index.append(ts)
                previous_close = float(close)

        return pd.DataFrame(rows, index=pd.DatetimeIndex(index))

    def test_strategy_reproduces_v13_entry_and_exit_timing(self):
        frame = self._build_frame()
        portal = DataPortal({SYMBOL: frame})
        config = BacktestConfig(
            symbols=[SYMBOL],
            initial_cash=100000.0,
            match_mode='next_open',
            enable_t1=True,
        )
        runner = BacktestRunner(config, portal)
        strategy = load_strategy(STRATEGY_PATH)

        results = runner.run(strategy)

        trades = results['trades']
        self.assertEqual(list(trades['side']), ['BUY', 'SELL'])
        self.assertEqual(list(trades['timestamp']), [datetime(2024, 10, 8, 14, 0), datetime(2024, 10, 9, 14, 0)])
        self.assertEqual(list(trades['price']), [94.0, 107.0])
        self.assertEqual(list(trades['quantity']), [100, 100])


if __name__ == '__main__':
    unittest.main()
