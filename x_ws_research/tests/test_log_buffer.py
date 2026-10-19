from services.log_buffer import LogBuffer


def test_log_buffer_respects_max():
    buf = LogBuffer(max_entries=3)
    for i in range(5):
        buf.append(f"msg-{i}")
    assert len(buf) == 3
    lines = buf.lines()
    assert "msg-2" in lines[0]
    assert "msg-4" in lines[-1]


def test_log_buffer_clear():
    buf = LogBuffer(max_entries=10)
    buf.append("a")
    buf.clear()
    assert len(buf) == 0
