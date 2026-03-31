import unittest

import pandas as pd

from event_driven_backtest.backend.tdx.indicators import CROSS, REF


class TdxIndicatorsTest(unittest.TestCase):
    def test_ref_returns_shifted_series(self):
        series = pd.Series([1, 2, 3])
        result = REF(series, 1)
        self.assertTrue(pd.isna(result.iloc[0]))
        self.assertEqual(result.iloc[1], 1)

    def test_cross_detects_upward_cross(self):
        a = pd.Series([1, 2])
        b = pd.Series([2, 1])
        result = CROSS(a, b)
        self.assertTrue(bool(result.iloc[-1]))


if __name__ == '__main__':
    unittest.main()
