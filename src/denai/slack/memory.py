"""Per-thread in-memory conversation store."""

from collections import defaultdict
from threading import Lock
from typing import Any


class ThreadMemory:
    def __init__(self, max_turns: int = 20) -> None:
        self._store: dict[str, list[dict[str, Any]]] = defaultdict(list)
        self._lock = Lock()
        self._max_turns = max_turns

    def key(self, channel_id: str, thread_ts: str | None) -> str:
        return f"{channel_id}:{thread_ts or 'root'}"

    def get(self, channel_id: str, thread_ts: str | None) -> list[dict[str, Any]]:
        with self._lock:
            return list(self._store[self.key(channel_id, thread_ts)])

    def set(self, channel_id: str, thread_ts: str | None, messages: list[dict[str, Any]]) -> None:
        with self._lock:
            self._store[self.key(channel_id, thread_ts)] = messages[-self._max_turns :]
