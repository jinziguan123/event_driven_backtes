import unittest

import pandas as pd

from event_driven_backtest.backend.data.aggregator import aggregate_bars


class AggregatorTest(unittest.TestCase):
    def test_aggregate_minute_to_5m_bar(self):
        df = pd.DataFrame(
            {
                'open': [1, 2, 3, 4, 5],
                'high': [2, 3, 4, 5, 6],
                'low': [1, 1, 2, 3, 4],
                'close': [2, 3, 4, 5, 6],
                'volume': [10, 10, 10, 10, 10],
                'amount': [100, 100, 100, 100, 100],
            },
            index=pd.date_range('2026-01-01 09:31:00', periods=5, freq='1min'),
        )
        result = aggregate_bars(df, '5min')
        self.assertEqual(result.iloc[0]['open'], 1)
        self.assertEqual(result.iloc[0]['close'], 6)
        self.assertEqual(result.iloc[0]['volume'], 50)


if __name__ == '__main__':
    unittest.main()
