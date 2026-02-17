"""
Очередь событий: доставки, списание fee, утренний отчёт.
Min-heap по timestamp (day * 1440 + minute_of_day).
"""
from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Any, List
import heapq


class EventType(str, Enum):
    DELIVERY = "delivery"           # заказ доставлен на склад
    DAILY_FEE = "daily_fee"        # списание ежедневного сбора
    DAY_START = "day_start"        # начало дня (доставки "утром")
    DAY_END = "day_end"             # конец дня (продажи, fee)


def _timestamp(day: int, minute: int) -> int:
    return day * 1440 + minute


@dataclass(order=True)
class Event:
    """Событие с приоритетом по времени."""
    ts: int  # для сортировки
    day: int
    minute: int
    kind: EventType
    payload: Any = field(compare=False)

    def __post_init__(self):
        if self.ts == 0:
            self.ts = _timestamp(self.day, self.minute)


class EventQueue:
    """Min-heap по ts."""
    def __init__(self):
        self._heap: List[Event] = []

    def push(self, event: Event) -> None:
        if event.ts == 0:
            event.ts = _timestamp(event.day, event.minute)
        heapq.heappush(self._heap, event)

    def pop(self) -> Event | None:
        if not self._heap:
            return None
        return heapq.heappop(self._heap)

    def peek(self) -> Event | None:
        if not self._heap:
            return None
        return self._heap[0]

    def pop_until(self, day: int, minute: int) -> list[Event]:
        """Извлечь все события до заданного времени (включительно)."""
        until_ts = _timestamp(day, minute)
        out = []
        while self._heap and self._heap[0].ts <= until_ts:
            out.append(heapq.heappop(self._heap))
        return out

    def __len__(self) -> int:
        return len(self._heap)
