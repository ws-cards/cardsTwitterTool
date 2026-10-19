"""GUI smoke tests with pytest-qt — no live X."""

from __future__ import annotations

import pytest
from PySide6.QtCore import Qt

from app.main_window import MainWindow
from schemas.task_state import TaskState


@pytest.fixture
def window(qtbot, data_root):
    win = MainWindow()
    qtbot.addWidget(win)
    win.show()
    yield win
    win.close()


def test_main_window_layout(window):
    assert window.left is not None
    assert window.monitor is not None
    assert window.windowTitle()
    assert window.left.btn_start.isEnabled()
    assert not window.left.btn_stop.isEnabled()


def test_task_state_controls_buttons(window):
    window._apply_task_state(TaskState.RUNNING)
    assert not window.left.btn_start.isEnabled()
    assert window.left.btn_stop.isEnabled()
    assert not window.act_start.isEnabled()
    assert window.act_stop.isEnabled()

    window._apply_task_state(TaskState.IDLE)
    assert window.left.btn_start.isEnabled()
    assert not window.left.btn_stop.isEnabled()


def test_log_append_has_cap(window):
    before = len(window.monitor.log_buffer)
    for i in range(20):
        window.monitor.append_log(f"line-{i}")
    assert len(window.monitor.log_buffer) == before + 20
    # Fill past max
    for i in range(600):
        window.monitor.append_log(f"overflow-{i}")
    assert len(window.monitor.log_buffer) == window.monitor.log_buffer.max_entries


def test_demo_task_completes(qtbot, window):
    from PySide6.QtCore import QMetaObject, Qt as QtCoreQt

    with qtbot.waitSignal(window._task_thread.worker.finished_ok, timeout=5000):
        QMetaObject.invokeMethod(
            window._task_thread.worker,
            "run_demo_task",
            QtCoreQt.ConnectionType.QueuedConnection,
        )
    assert window._task_state == TaskState.COMPLETED
    assert window.left.btn_start.isEnabled()
