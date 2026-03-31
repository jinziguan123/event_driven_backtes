from pathlib import Path
from tempfile import TemporaryDirectory
import unittest

from event_driven_backtest.backend.storage.result_store import ResultStore


class ResultStoreTest(unittest.TestCase):
    def test_result_store_creates_run_directory(self):
        with TemporaryDirectory() as temp_dir:
            store = ResultStore(base_dir=temp_dir, db_backend='sqlite')
            run_id = store.create_run_directory()
            self.assertTrue(Path(temp_dir, run_id).exists())

    def test_save_logs_writes_jsonl(self):
        with TemporaryDirectory() as temp_dir:
            store = ResultStore(base_dir=temp_dir, db_backend='sqlite')
            run_id = store.create_run_directory()
            path = store.save_logs(run_id, [{'level': 'INFO', 'message': 'hello'}])
            self.assertTrue(path.exists())
            self.assertIn('hello', path.read_text(encoding='utf-8'))

    def test_delete_run_removes_metadata_and_directory(self):
        with TemporaryDirectory() as temp_dir:
            store = ResultStore(base_dir=temp_dir, db_backend='sqlite')
            run_id = store.create_run_directory()
            store.register_run(run_id, name='待删除', strategy_name='demo', status='SUCCESS', params={'symbols': ['000001.SZ']})
            store.save_logs(run_id, [{'level': 'INFO', 'message': 'to-delete'}])

            deleted = store.delete_run(run_id)

            self.assertTrue(deleted)
            self.assertIsNone(store.get_run_row(run_id))
            self.assertFalse(Path(temp_dir, run_id).exists())


if __name__ == '__main__':
    unittest.main()
