"""Bounded in-memory log buffer for the UI."""

from __future__ import annotations

from collections import deque
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Deque, Iterable


@dataclass(frozen=True)
class LogEntry:
    timestamp: datetime
    level: str
    message: str

    def format(self) -> str:
        ts = self.timestamp.strftime("%H:%M:%S")
        return f"[{ts}] [{self.level}] {self.message}"


class LogBuffer:
    """Ring buffer of log lines with a hard upper bound."""

    def __init__(self, max_entries: int = 500) -> None:
        if max_entries < 1:
            raise ValueError("max_entries must be >= 1")
        self._max = max_entries
        self._entries: Deque[LogEntry] = deque(maxlen=max_entries)

    @property
    def max_entries(self) -> int:
        return self._max

    def __len__(self) -> int:
        return len(self._entries)

    def clear(self) -> None:
        self._entries.clear()

    def append(self, message: str, level: str = "INFO") -> LogEntry:
        entry = LogEntry(
            timestamp=datetime.now(timezone.utc),
            level=level.upper(),
            message=message,
        )
        self._entries.append(entry)
        return entry

    def lines(self) -> list[str]:
        return [e.format() for e in self._entries]

    def extend(self, messages: Iterable[str], level: str = "INFO") -> None:
        for msg in messages:
            self.append(msg, level=level)
