"""Unit tests for SessionBuffer and SessionManager (T11-002)."""

from streaming.session_manager import SessionBuffer, SessionManager, slugify_device


def test_slugify_device():
    assert slugify_device("Samsung Galaxy S21") == "samsung-galaxy-s21"
    assert slugify_device("Redmi Note 10") == "redmi-note-10"
    assert slugify_device("") == "device"


def test_duplicate_seq_adds_no_row():
    """Duplicate sequence numbers must be ignored and not add duplicate rows."""
    buffer = SessionBuffer(client_id="client-1", session_id="samsung-1", device="Samsung")

    row = {
        "timestamp": "2026-10-09 10:15:00",
        "device": "Samsung",
        "ss_rsrp": -95.0,
        "ss_rsrq": -11.0,
        "ss_sinr": 18.5,
    }

    added_first = buffer.append(row, seq=100)
    assert added_first is True
    assert len(buffer) == 1
    assert buffer.has_seq(100) is True
    assert buffer.last_seq == 100

    # Attempt to append duplicate seq 100
    added_duplicate = buffer.append(row, seq=100)
    assert added_duplicate is False
    assert len(buffer) == 1

    # Appending higher seq succeeds
    added_next = buffer.append(row, seq=101)
    assert added_next is True
    assert len(buffer) == 2
    assert buffer.last_seq == 101


def test_out_of_order_arrivals_ordered_by_timestamp():
    """Samples arriving out of order must be ordered by device timestamp."""
    buffer = SessionBuffer(client_id="client-1", session_id="samsung-1", device="Samsung")

    # Sample 1: t = 10:15:06 (seq 2 arrives first)
    row_t2 = {
        "timestamp": "2026-10-09 10:15:06",
        "device": "Samsung",
        "ss_rsrp": -96.0,
        "seq": 2,
    }
    # Sample 2: t = 10:15:00 (seq 1 arrives second)
    row_t1 = {
        "timestamp": "2026-10-09 10:15:00",
        "device": "Samsung",
        "ss_rsrp": -90.0,
        "seq": 1,
    }
    # Sample 3: t = 10:15:03 (seq 3 arrives third, between t1 and t2)
    row_t3 = {
        "timestamp": "2026-10-09 10:15:03",
        "device": "Samsung",
        "ss_rsrp": -93.0,
        "seq": 3,
    }

    assert buffer.append(row_t2, seq=2) is True
    assert buffer.append(row_t1, seq=1) is True
    assert buffer.append(row_t3, seq=3) is True

    assert len(buffer) == 3

    df = buffer.to_dataframe()
    timestamps = list(df["timestamp"])
    assert timestamps == sorted(timestamps)

    # Check that sample_idx starts at 0 and increments strictly
    assert list(df["sample_idx"]) == [0, 1, 2]
    # Check that t1 (-90.0) is row 0, t3 (-93.0) is row 1, t2 (-96.0) is row 2
    assert list(df["ss_rsrp"]) == [-90.0, -93.0, -96.0]


def test_rollover_at_cap(caplog):
    """When a session buffer reaches max_rows, SessionManager closes it and rolls to new session."""
    mgr = SessionManager(max_rows=3)

    sample_base = {
        "device": "Samsung",
        "ss_rsrp": -95.0,
    }

    # Append 3 samples to fill the cap
    for seq in range(1, 4):
        sample = dict(sample_base, timestamp=f"2026-10-09 10:15:0{seq}")
        buf, appended = mgr.append_sample(client_id="phone-a", row=sample, seq=seq)
        assert appended is True
        assert buf.session_id == "samsung-1"
        assert len(buf) == seq

    assert buf.is_full() is True

    # 4th sample must trigger rollover to samsung-2
    sample_4 = dict(sample_base, timestamp="2026-10-09 10:15:04")
    with caplog.at_level("WARNING"):
        buf_4, appended_4 = mgr.append_sample(client_id="phone-a", row=sample_4, seq=4)

    assert appended_4 is True
    assert buf_4.session_id == "samsung-2"
    assert len(buf_4) == 1
    assert "reached cap (3 rows); rolling over" in caplog.text


def test_injectable_clock():
    """SessionBuffer and SessionManager use injected clock."""
    current_time = 1700000000.0

    def mock_clock() -> float:
        return current_time

    buffer = SessionBuffer(
        client_id="c1",
        session_id="s1",
        device="Samsung",
        clock=mock_clock,
    )
    assert buffer.created_at == 1700000000.0
    assert buffer.last_active_at == 1700000000.0

    # Advance time and append
    current_time = 1700000050.0
    buffer.append({"timestamp": "2026-10-09 10:15:00"}, seq=1)
    assert buffer.last_active_at == 1700000050.0


def test_client_isolation():
    """Different clients have completely isolated session buffers."""
    mgr = SessionManager(max_rows=10)

    buf_a, _ = mgr.append_sample(
        "client-a", {"timestamp": "2026-10-09 10:15:00", "device": "Redmi"}, seq=1
    )
    buf_b, _ = mgr.append_sample(
        "client-b", {"timestamp": "2026-10-09 10:15:00", "device": "Samsung"}, seq=1
    )

    assert buf_a.session_id == "redmi-1"
    assert buf_b.session_id == "samsung-1"
    assert len(buf_a) == 1
    assert len(buf_b) == 1
