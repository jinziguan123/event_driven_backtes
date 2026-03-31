from pathlib import Path
from tempfile import TemporaryDirectory
import time
import unittest

from event_driven_backtest.backend.strategy_sdk.discovery import clear_strategy_cache, list_strategy_files


class StrategyDiscoveryTest(unittest.TestCase):
    def test_list_strategy_files_uses_directory_cache_and_refreshes_on_change(self):
        with TemporaryDirectory() as temp_dir:
            strategy_dir = Path(temp_dir)
            clear_strategy_cache()
            (strategy_dir / 'alpha.py').write_text('name = "alpha"\n', encoding='utf-8')

            first = list_strategy_files(strategy_dir=strategy_dir)
            self.assertEqual([item['name'] for item in first], ['alpha'])

            (strategy_dir / 'beta.py').write_text('name = "beta"\n', encoding='utf-8')
            second = list_strategy_files(strategy_dir=strategy_dir)
            self.assertEqual([item['name'] for item in second], ['alpha'])

            time.sleep(1.1)
            (strategy_dir / 'beta.py').write_text('name = "beta"\n# refresh\n', encoding='utf-8')
            refreshed = list_strategy_files(strategy_dir=strategy_dir)
            self.assertEqual([item['name'] for item in refreshed], ['alpha', 'beta'])

    def test_list_strategy_files_includes_fibonacci_ema_v13(self):
        clear_strategy_cache()

        strategies = list_strategy_files()

        self.assertIn('fibonacci_ema_v13', [item['name'] for item in strategies])


if __name__ == '__main__':
    unittest.main()
