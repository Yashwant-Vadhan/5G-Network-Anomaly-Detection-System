"""Unit tests for live fan-out hub (T11-013)."""

import time

import pytest

from streaming.hub import LiveHub
from streaming.schema import DroppedEvent


@pytest.fixture
def anyio_backend():
    return "asyncio"


@pytest.mark.anyio
async def test_slow_subscriber_never_blocks_publisher():
    """Slow subscriber queue overflow must never block broadcast calls."""
    hub = LiveHub(default_queue_size=5)

    sub_id, _ = await hub.subscribe(queue_size=3)

    t0 = time.perf_counter()
    # Publish 50 messages rapidly into a queue of size 3
    for i in range(50):
        await hub.broadcast({"msg": f"sample-{i}"}, session_id="test-session-1")
    t1 = time.perf_counter()

    # Must complete almost instantly (never blocked by unread queue)
    assert (t1 - t0) < 0.2
    await hub.unsubscribe(sub_id)


@pytest.mark.anyio
async def test_dropped_event_emitted_with_count():
    """When a subscriber queue overflows, a DroppedEvent with accurate count is emitted."""
    hub = LiveHub(default_queue_size=3)

    sub_id, queue = await hub.subscribe(queue_size=3)

    # Publish 10 messages into a queue of capacity 3
    for i in range(10):
        await hub.broadcast({"idx": i}, session_id="session-overflow")

    # Read all remaining items in the queue
    items = []
    while not queue.empty():
        items.append(await queue.get())

    # Verify that a DroppedEvent was emitted in the queue
    dropped_events = [item for item in items if isinstance(item, DroppedEvent)]
    assert len(dropped_events) >= 1
    assert dropped_events[-1].count >= 1
    assert dropped_events[-1].type == "dropped"
    assert dropped_events[-1].session_id == "session-overflow"

    await hub.unsubscribe(sub_id)


@pytest.mark.anyio
async def test_subscriber_cleanup_no_leaks():
    """Unsubscribing clients correctly removes them from hub registry."""
    hub = LiveHub(default_queue_size=10)

    sub1_id, _ = await hub.subscribe()
    sub2_id, _ = await hub.subscribe()
    assert hub.subscriber_count == 2

    # Unsubscribe sub1
    removed1 = await hub.unsubscribe(sub1_id)
    assert removed1 is True
    assert hub.subscriber_count == 1

    # Unsubscribe already removed sub1
    removed_again = await hub.unsubscribe(sub1_id)
    assert removed_again is False

    # Unsubscribe sub2
    removed2 = await hub.unsubscribe(sub2_id)
    assert removed2 is True
    assert hub.subscriber_count == 0


@pytest.mark.anyio
async def test_normal_subscriber_receives_all_messages():
    """Fast subscriber keeping up receives all broadcast messages."""
    hub = LiveHub(default_queue_size=20)

    sub_id, queue = await hub.subscribe(queue_size=20)

    for i in range(5):
        await hub.broadcast({"counter": i})

    received = []
    for _ in range(5):
        msg = await queue.get()
        received.append(msg["counter"])

    assert received == [0, 1, 2, 3, 4]
    await hub.unsubscribe(sub_id)
