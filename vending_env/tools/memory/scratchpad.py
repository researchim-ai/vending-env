"""
Scratchpad: запись и чтение последних K записей (план 7.1).
Без явных ограничений по размеру, как в статье.
"""
from __future__ import annotations

from collections import deque
from typing import Optional


class Scratchpad:
    def __init__(self, max_entries: int = 1000):
        self._entries: deque = deque(maxlen=max_entries)

    def write(self, text: str) -> str:
        self._entries.append(text.strip())
        return "Written."

    def read(self, last_k: int = 10) -> str:
        if not self._entries:
            return ""
        k = min(last_k, len(self._entries))
        return "\n---\n".join(list(self._entries)[-k:])

    def clear(self) -> str:
        self._entries.clear()
        return "Cleared."
