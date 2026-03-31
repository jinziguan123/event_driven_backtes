from pathlib import Path
import unittest


class ScaffoldTest(unittest.TestCase):
    def test_project_scaffold_exists(self):
        self.assertTrue(Path('event_driven_backtest/backend').exists())
        self.assertTrue(Path('event_driven_backtest/frontend/src').exists())


if __name__ == '__main__':
    unittest.main()
