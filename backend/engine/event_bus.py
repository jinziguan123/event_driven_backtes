from __future__ import annotations

from collections import defaultdict
from collections.abc import Callable

from event_driven_backtest.backend.core.events import Event, EventType


class EventBus:
    def __init__(self) -> None:
        self._subscribers: dict[EventType, list[Callable[[Event], None]]] = defaultdict(list)

    def subscribe(self, event_type: EventType, handler: Callable[[Event], None]) -> None:
        self._subscribers[event_type].append(handler)

    def publish(self, event: Event) -> None:
        for handler in self._subscribers.get(event.type, []):
            handler(event)
