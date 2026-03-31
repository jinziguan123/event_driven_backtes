import json
import unittest

from event_driven_backtest.backend.runner.stream_hub import RunStreamHub


class RunStreamHubTest(unittest.TestCase):
    def test_publish_then_consume_stream_event(self):
        hub = RunStreamHub()
        hub.ensure_run('run_1', {'status': 'RUNNING', 'logs': [], 'equity': []})
        hub.publish('run_1', 'log', {'message': 'hello'})

        event_stream = hub.subscribe('run_1')
        first_chunk = next(event_stream)
        second_chunk = next(event_stream)

        self.assertIn('event: snapshot', first_chunk)
        self.assertIn('event: log', second_chunk)
        payload = second_chunk.split('data: ', 1)[1].strip()
        self.assertEqual(json.loads(payload)['message'], 'hello')

    def test_append_snapshot_data_updates_current_state(self):
        hub = RunStreamHub()
        hub.ensure_run('run_2', {'status': 'RUNNING', 'logs': [], 'equity': []})
        hub.append_item('run_2', 'logs', {'message': 'step'})
        hub.append_item('run_2', 'equity', {'timestamp': '2026-03-10T10:00:00', 'total_equity': 1000000})

        snapshot = hub.get_snapshot('run_2')
        self.assertEqual(snapshot['logs'][0]['message'], 'step')
        self.assertEqual(snapshot['equity'][0]['total_equity'], 1000000)


if __name__ == '__main__':
    unittest.main()
