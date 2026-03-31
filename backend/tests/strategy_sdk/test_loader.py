from pathlib import Path
import unittest

from event_driven_backtest.backend.strategy_sdk.loader import load_strategy


FIXTURE_DIR = Path('event_driven_backtest/backend/tests/fixtures')
STRATEGY_DIR = Path('event_driven_backtest/backend/strategies')


class StrategyLoaderTest(unittest.TestCase):
    def test_load_class_strategy(self):
        strategy = load_strategy(FIXTURE_DIR / 'sample_class_strategy.py')
        self.assertTrue(hasattr(strategy, 'on_bar'))
        self.assertEqual(strategy.name, 'sample_class')

    def test_load_script_strategy(self):
        strategy = load_strategy(FIXTURE_DIR / 'sample_script_strategy.py')
        self.assertTrue(hasattr(strategy, 'on_bar'))
        self.assertEqual(strategy.name, 'sample_script')

    def test_load_minute_sma_strategy(self):
        strategy = load_strategy(STRATEGY_DIR / 'minute_sma_5_20.py')
        self.assertTrue(hasattr(strategy, 'on_bar'))
        self.assertEqual(strategy.name, 'minute_sma_5_20')

    def test_load_fibonacci_ema_v13_strategy(self):
        strategy = load_strategy(STRATEGY_DIR / 'fibonacci_ema_v13.py')
        self.assertTrue(hasattr(strategy, 'on_bar'))
        self.assertEqual(strategy.name, 'fibonacci_ema_v13')


if __name__ == '__main__':
    unittest.main()
