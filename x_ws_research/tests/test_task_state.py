from schemas.task_state import TaskState


def test_can_start_states():
    assert TaskState.IDLE.can_start
    assert TaskState.COMPLETED.can_start
    assert TaskState.CANCELLED.can_start
    assert TaskState.FAILED.can_start
    assert not TaskState.RUNNING.can_start
    assert not TaskState.INITIALIZING.can_start
    assert not TaskState.STOPPING.can_start


def test_can_stop_states():
    assert TaskState.RUNNING.can_stop
    assert TaskState.INITIALIZING.can_stop
    assert not TaskState.IDLE.can_stop
    assert not TaskState.COMPLETED.can_stop


def test_busy_flag():
    assert TaskState.RUNNING.is_busy
    assert TaskState.STOPPING.is_busy
    assert not TaskState.IDLE.is_busy
