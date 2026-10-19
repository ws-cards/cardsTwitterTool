"""Task lifecycle states for UI and worker coordination."""

from __future__ import annotations

from enum import Enum


class TaskState(str, Enum):
    """Canonical task states. Buttons are enabled/disabled from this enum."""

    IDLE = "IDLE"
    INITIALIZING = "INITIALIZING"
    RUNNING = "RUNNING"
    STOPPING = "STOPPING"
    COMPLETED = "COMPLETED"
    CANCELLED = "CANCELLED"
    FAILED = "FAILED"

    @property
    def can_start(self) -> bool:
        return self in {
            TaskState.IDLE,
            TaskState.COMPLETED,
            TaskState.CANCELLED,
            TaskState.FAILED,
        }

    @property
    def can_stop(self) -> bool:
        return self in {TaskState.INITIALIZING, TaskState.RUNNING}

    @property
    def is_terminal(self) -> bool:
        return self in {
            TaskState.COMPLETED,
            TaskState.CANCELLED,
            TaskState.FAILED,
            TaskState.IDLE,
        }

    @property
    def is_busy(self) -> bool:
        return self in {
            TaskState.INITIALIZING,
            TaskState.RUNNING,
            TaskState.STOPPING,
        }
