import asyncio
from collections import defaultdict


class EventBus:
    _instance = None

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls._instance._subscribers = defaultdict(list)
            cls._instance._lock = asyncio.Lock()
        return cls._instance

    def subscribe(self, event_type: str, callback):
        self._subscribers[event_type].append(callback)

    def unsubscribe(self, event_type: str, callback):
        try:
            self._subscribers[event_type].remove(callback)
        except ValueError:
            pass

    async def publish(self, event_type: str, data=None):
        for cb in self._subscribers[event_type]:
            try:
                await cb(data)
            except Exception as e:
                print(f"[event_bus] Error in {event_type} handler: {e}")
