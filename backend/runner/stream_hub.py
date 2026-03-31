from __future__ import annotations

import json
from copy import deepcopy
from datetime import date, datetime
from queue import Empty, Queue
from threading import RLock
from typing import Iterator

TERMINAL_STATUSES = {'SUCCESS', 'FAILED', 'CANCELED'}


class RunStreamHub:
    def __init__(self):
        self._lock = RLock()
        self._states: dict[str, dict] = {}
        self._history: dict[str, list[tuple[str, dict]]] = {}
        self._subscribers: dict[str, list[Queue[tuple[str, str] | None]]] = {}

    def has_run(self, run_id: str) -> bool:
        with self._lock:
            return run_id in self._states

    def ensure_run(self, run_id: str, initial_state: dict | None = None) -> dict:
        with self._lock:
            if run_id not in self._states:
                self._states[run_id] = deepcopy(initial_state or {})
            elif initial_state:
                for key, value in initial_state.items():
                    self._states[run_id].setdefault(key, deepcopy(value))
            self._history.setdefault(run_id, [])
            self._subscribers.setdefault(run_id, [])
            return deepcopy(self._states[run_id])

    def update_state(self, run_id: str, patch: dict) -> dict:
        with self._lock:
            self.ensure_run(run_id, {})
            self._states[run_id].update(deepcopy(patch))
            return deepcopy(self._states[run_id])

    def append_item(self, run_id: str, key: str, item: dict) -> list[dict]:
        with self._lock:
            self.ensure_run(run_id, {})
            items = self._states[run_id].setdefault(key, [])
            items.append(deepcopy(item))
            return deepcopy(items)

    def get_snapshot(self, run_id: str) -> dict:
        with self._lock:
            state = self._states.get(run_id)
            return deepcopy(state) if state is not None else {}

    def publish(self, run_id: str, event: str, payload: dict) -> str:
        chunk = self._format_sse(event, payload)
        with self._lock:
            self.ensure_run(run_id, {})
            self._history[run_id].append((event, deepcopy(payload)))
            subscribers = list(self._subscribers.get(run_id, []))
        for subscriber in subscribers:
            subscriber.put((event, chunk))
        return chunk

    def subscribe(self, run_id: str) -> Iterator[str]:
        queue: Queue[tuple[str, str] | None] = Queue()
        with self._lock:
            self.ensure_run(run_id, {})
            snapshot = deepcopy(self._states[run_id])
            history = list(self._history.get(run_id, []))
            is_terminal = snapshot.get('status') in TERMINAL_STATUSES
            if not is_terminal:
                self._subscribers[run_id].append(queue)

        yield self._format_sse('snapshot', snapshot)
        for event, payload in history:
            yield self._format_sse(event, payload)

        if is_terminal:
            return

        try:
            while True:
                try:
                    item = queue.get(timeout=1.0)
                except Empty:
                    if self.get_snapshot(run_id).get('status') in TERMINAL_STATUSES:
                        return
                    continue
                if item is None:
                    return
                event, chunk = item
                yield chunk
                if event == 'complete':
                    return
        finally:
            with self._lock:
                subscribers = self._subscribers.get(run_id, [])
                if queue in subscribers:
                    subscribers.remove(queue)

    def remove_run(self, run_id: str) -> None:
        with self._lock:
            subscribers = self._subscribers.pop(run_id, [])
            self._states.pop(run_id, None)
            self._history.pop(run_id, None)
        for subscriber in subscribers:
            subscriber.put(None)

    @staticmethod
    def _json_default(value):
        if isinstance(value, (datetime, date)):
            return value.isoformat()
        return str(value)

    @classmethod
    def _format_sse(cls, event: str, payload: dict) -> str:
        data = json.dumps(payload, ensure_ascii=False, default=cls._json_default)
        return f'event: {event}\ndata: {data}\n\n'
