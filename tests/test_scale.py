"""Capacity follows counted bytes, and a second turn opens another engine."""

import threading
import time

from chorusgraph.transport.chorus import ChorusSpine

from cpu_llm.pipeline import TENSOR_DIM
from cpu_llm.scale import (
    ENGINE_PROCESSES,
    TENSOR_BYTES,
    THINKER_HEADS,
    EngineManager,
    chunk_footprint,
    performance_matrix,
    scale_order,
)
from cpu_llm.thinker_pool import _HEADS


def test_the_matrix_counts_the_tensor_and_the_text():
    assert TENSOR_DIM == 1024
    assert TENSOR_BYTES == 4096
    assert THINKER_HEADS == len(_HEADS)
    assert ENGINE_PROCESSES == THINKER_HEADS + 1
    one = chunk_footprint("late shipment")
    assert one.tensor_bytes == 4096
    assert one.text_bytes == len("late shipment".encode())
    assert one.stored_bytes > one.tensor_bytes + one.text_bytes
    rows = performance_matrix(
        ["late shipment", "late shipment"],
        available_bytes=one.stored_bytes,
        cpu_count=4,
    )
    assert [row.chunks for row in rows] == [1, 2]
    assert rows[0].stored_bytes == one.stored_bytes
    assert rows[0].engines == 1
    assert rows[0].place == "this_server"
    assert rows[1].tensor_bytes == 8192
    assert rows[1].stored_bytes == one.stored_bytes * 2
    assert rows[1].engines == 2
    assert rows[1].thinker_processes == 10
    assert rows[1].place == "other_server"


def test_scale_holds_until_memory_or_a_waiting_turn():
    hold = scale_order(
        stored_bytes=100,
        available_bytes=1000,
        cpu_count=16,
        engines=1,
        busy=False,
        waiting=0,
    )
    assert hold.action == "hold"
    memory = scale_order(
        stored_bytes=5000,
        available_bytes=1000,
        cpu_count=16,
        engines=1,
        busy=False,
        waiting=0,
    )
    assert memory.action == "add_engine"
    assert memory.engines == 5
    assert memory.place == "other_server"
    assert memory.reason == "stored chunks are larger than the available memory"
    same = scale_order(
        stored_bytes=100,
        available_bytes=1000,
        cpu_count=16,
        engines=1,
        busy=True,
        waiting=1,
    )
    assert same.action == "add_engine"
    assert same.place == "this_server"
    assert same.thinker_processes == 10
    other = scale_order(
        stored_bytes=100,
        available_bytes=1000,
        cpu_count=8,
        engines=1,
        busy=True,
        waiting=1,
    )
    assert other.place == "other_server"


def test_the_manager_opens_a_seat_and_shares_the_chunk_over_the_fabric():
    spine = ChorusSpine(tenant_id="cpu-llm")
    manager = EngineManager(spine, cpu_count=8, available_bytes=10**9, read_workers=2, write_workers=2)
    try:
        order = manager.ensure_capacity(busy=True)
        manager._waiting = 1
        order = manager.ensure_capacity(busy=True)
        assert order.action == "add_engine"
        assert order.place == "other_server"
        assert [seat.place for seat in manager.seats] == ["this_server", "other_server"]
        frame = manager.publish_chunk("c0", "The late shipment left the dock.", seat_id="engine-1")
        assert frame.metadata["tensor_dim"] == 1024
        assert frame.metadata["tensor_bytes"] == 4096
        assert len(frame.vector_64) == 64
        assert spine._sent[-1].artifact_ref == "c0"
        peer = EngineManager(cpu_count=8, available_bytes=10**9)
        try:
            seat_id = peer.receive(
                {
                    "type": "chorus_frame",
                    "artifact_ref": frame.artifact_ref,
                    "metadata": frame.metadata,
                    "to_hop": "engine-1",
                }
            )
            assert seat_id == "engine-1"
            assert peer.catalog["c0"] == "engine-1"
            assert peer.stored_bytes() == chunk_footprint("The late shipment left the dock.").stored_bytes
        finally:
            peer.close()
    finally:
        manager.close()


def test_writes_take_the_thinker_one_at_a_time():
    manager = EngineManager(cpu_count=4, available_bytes=10**9, write_workers=2)
    seen: list[str] = []
    gate = threading.Event()
    try:
        def first() -> str:
            seen.append("start")
            gate.wait(1)
            seen.append("end")
            return "first"

        def second() -> str:
            seen.append("second")
            return "second"

        left = manager.submit_write(first)
        time.sleep(0.05)
        right = manager.submit_write(second)
        time.sleep(0.05)
        assert seen == ["start"]
        gate.set()
        assert left.result(timeout=2) == "first"
        assert right.result(timeout=2) == "second"
        assert seen == ["start", "end", "second"]
        assert manager.submit_read(lambda: "read").result(timeout=2) == "read"
    finally:
        gate.set()
        manager.close()
