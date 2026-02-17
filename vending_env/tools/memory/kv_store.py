"""
Key-value store для агента (план 7.1).
"""
from __future__ import annotations

from typing import Dict, Optional


class KVStore:
    def __init__(self):
        self._store: Dict[str, str] = {}

    def put(self, key: str, value: str) -> str:
        self._store[key.strip()] = str(value)
        return "OK"

    def get(self, key: str) -> str:
        return self._store.get(key.strip(), "")

    def delete(self, key: str) -> str:
        k = key.strip()
        if k in self._store:
            del self._store[k]
            return "Deleted."
        return "Key not found."

    def keys(self) -> list:
        return list(self._store.keys())
