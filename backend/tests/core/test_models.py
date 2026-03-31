from datetime import datetime
import unittest

from event_driven_backtest.backend.core.config import BacktestConfig
from event_driven_backtest.backend.core.events import EventType
from event_driven_backtest.backend.core.models import MarketBar


class CoreModelsTest(unittest.TestCase):
    def test_backtest_config_defaults(self):
        config = BacktestConfig(symbols=['000001.SZ'])
        self.assertGreater(config.initial_cash, 0)
        self.assertGreaterEqual(config.max_positions, 1)
        self.assertIn(config.match_mode, {'close', 'next_open', 'limit'})

    def test_market_bar_fields(self):
        bar = MarketBar(
            symbol='000001.SZ',
            datetime=datetime(2026, 1, 1, 9, 35),
            open=1,
            high=2,
            low=1,
            close=2,
            volume=3,
            amount=4,
        )
        self.assertEqual(bar.symbol, '000001.SZ')
        self.assertEqual(bar.close, 2)

    def test_event_type_contains_bar_close(self):
        self.assertEqual(EventType.BAR_CLOSE.value, 'BAR_CLOSE')


if __name__ == '__main__':
    unittest.main()
