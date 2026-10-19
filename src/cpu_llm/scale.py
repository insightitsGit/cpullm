"""Capacity of one engine, and the manager that adds another.

A stored chunk carries one 1024-d float32 tensor, 4096 bytes, plus the
UTF-8 text and the JSON ChorusGraph writes for that node. Those sizes are
counted here. Nothing in this module is a timed benchmark.

One engine runs one thinker turn at a time. ``WarmEvaluatorPool`` holds its
lock across the five heads, so a second turn is a second engine, not a second
thread inside that lock. The five heads of a single turn already run together.

PrismCortex splits reads and writes into two pools and keeps a manager in
front of tenant memories. This manager does the same for engines. Engines on
this machine or another machine share one catalog through a CHORUS fabric
spine: the frame names the chunk, and the text and the byte counts ride in
the frame. The 64-wide fabric slot is not a replacement for the 1024-d tensor.
"""

from __future__ import annotations

import argparse
import os
import threading
from datetime import datetime, timezone
from concurrent.futures import Future, ThreadPoolExecutor
from dataclasses import dataclass
from typing import Any, Callable, Optional

from chorusgraph.transport.chorus import ChorusFrame, ChorusSpine

TENSOR_DIM = 1024
TENSOR_BYTES = TENSOR_DIM * 4
THINKER_HEADS = 5
ENGINE_PROCESSES = THINKER_HEADS + 1
FABRIC_WIDTH = 64


@dataclass(frozen=True)
class ChunkFootprint:
    """Bytes one chunk adds. ``tensor_bytes`` is the float32 array. ``stored_bytes`` is the JSON node."""

    text_bytes: int
    tensor_bytes: int
    stored_bytes: int


@dataclass(frozen=True)
class MatrixRow:
    chunks: int
    text_bytes: int
    tensor_bytes: int
    stored_bytes: int
    engines: int
    thinker_processes: int
    place: str


@dataclass(frozen=True)
class MachineBudget:
    cpu_count: int
    available_bytes: int


@dataclass(frozen=True)
class ScaleOrder:
    """What to do at this size. ``hold`` stays on the engines already open."""

    action: str
    place: str
    reason: str
    stored_bytes: int
    available_bytes: int
    cpu_count: int
    engines: int
    thinker_processes: int


@dataclass
class Seat:
    """One engine. ``place`` is ``this_server`` or ``other_server``."""

    id: str
    place: str
    host: str
    chunks: int = 0
    text_bytes: int = 0
    stored_bytes: int = 0
    busy: bool = False


def chunk_footprint(text: str) -> ChunkFootprint:
    """Count one chunk from its text. The tensor width is the retrieval contract, 1024 float32 values."""
    raw = text or ""
    text_bytes = len(raw.encode("utf-8"))
    stored = _node_json_bytes(raw)
    return ChunkFootprint(text_bytes=text_bytes, tensor_bytes=TENSOR_BYTES, stored_bytes=stored)


def performance_matrix(
    texts: list[str],
    *,
    available_bytes: int,
    cpu_count: int,
) -> list[MatrixRow]:
    """One row per chunk count, using the texts in order. Engines split the stored bytes across machines."""
    rows: list[MatrixRow] = []
    text_bytes = 0
    stored = 0
    for count, text in enumerate(texts, start=1):
        foot = chunk_footprint(text)
        text_bytes += foot.text_bytes
        stored += foot.stored_bytes
        engines = _engines_for(stored, available_bytes)
        rows.append(
            MatrixRow(
                chunks=count,
                text_bytes=text_bytes,
                tensor_bytes=TENSOR_BYTES * count,
                stored_bytes=stored,
                engines=engines,
                thinker_processes=engines * THINKER_HEADS,
                place=_place(cpu_count, engines),
            )
        )
    return rows


def machine_budget() -> MachineBudget:
    """CPUs and available physical bytes reported by this machine."""
    return MachineBudget(cpu_count=os.cpu_count() or 1, available_bytes=_available_bytes())


def scale_order(
    *,
    stored_bytes: int,
    available_bytes: int,
    cpu_count: int,
    engines: int,
    busy: bool,
    waiting: int,
) -> ScaleOrder:
    """Hold, or add an engine. Memory that does not fit, or a second turn while this engine is busy."""
    open_engines = max(1, engines)
    needed = _engines_for(stored_bytes, available_bytes)
    if busy and waiting > 0:
        needed = max(needed, open_engines + 1)
    if needed > open_engines:
        reason = (
            "this engine is in a thinker turn and another turn is waiting"
            if busy and waiting > 0 and _engines_for(stored_bytes, available_bytes) <= open_engines
            else "stored chunks are larger than the available memory"
        )
        return ScaleOrder(
            action="add_engine",
            place=_place(cpu_count, needed),
            reason=reason,
            stored_bytes=stored_bytes,
            available_bytes=available_bytes,
            cpu_count=cpu_count,
            engines=needed,
            thinker_processes=needed * THINKER_HEADS,
        )
    return ScaleOrder(
        action="hold",
        place="this_server" if open_engines == 1 else _place(cpu_count, open_engines),
        reason="the open engines cover this size",
        stored_bytes=stored_bytes,
        available_bytes=available_bytes,
        cpu_count=cpu_count,
        engines=open_engines,
        thinker_processes=open_engines * THINKER_HEADS,
    )


class EngineManager:
    """Seats, a read pool, a write pool, and one CHORUS spine between them.

    The write pool is the scarce side, matching PrismCortex's digest pool.
    A seat runs one write at a time. Reads use the other pool. A new seat on
    another server is reached by a fabric frame; the manager's catalog is the
    shared memory of chunk ids, texts, and byte counts.
    """

    def __init__(
        self,
        spine: ChorusSpine | None = None,
        *,
        cpu_count: int | None = None,
        available_bytes: int | None = None,
        read_workers: int | None = None,
        write_workers: int | None = None,
        host: str = "local",
    ) -> None:
        budget = machine_budget()
        self.cpu_count = budget.cpu_count if cpu_count is None else cpu_count
        self.available_bytes = budget.available_bytes if available_bytes is None else available_bytes
        self.spine = spine or ChorusSpine(tenant_id="cpu-llm")
        self.host = host
        self.seats: list[Seat] = [Seat(id="engine-0", place="this_server", host=host)]
        self.catalog: dict[str, str] = {}
        self._waiting = 0
        self._lock = threading.Lock()
        self._turn = threading.Semaphore(1)
        reads = read_workers if read_workers is not None else _pool_size("CPU_LLM_READ_POOL", min(4, self.cpu_count))
        writes = write_workers if write_workers is not None else _pool_size("CPU_LLM_WRITE_POOL", 1)
        self.read_pool = ThreadPoolExecutor(max_workers=max(1, reads), thread_name_prefix="cpu-llm-read")
        self.write_pool = ThreadPoolExecutor(max_workers=max(1, writes), thread_name_prefix="cpu-llm-write")

    def close(self) -> None:
        self.read_pool.shutdown(wait=False, cancel_futures=True)
        self.write_pool.shutdown(wait=False, cancel_futures=True)

    def stored_bytes(self) -> int:
        return sum(seat.stored_bytes for seat in self.seats)

    def submit_read(self, fn: Callable[[], Any]) -> Future[Any]:
        return self.read_pool.submit(fn)

    def submit_write(self, fn: Callable[[], Any]) -> Future[Any]:
        with self._lock:
            self._waiting += 1
        return self.write_pool.submit(self._run_write, fn)

    def ensure_capacity(self, *, busy: bool | None = None) -> ScaleOrder:
        """Open another seat when the scale order says the current seats are not enough."""
        with self._lock:
            waiting = self._waiting
            engines = len(self.seats)
            busy_now = self.seats[0].busy if busy is None else busy
            stored = sum(seat.stored_bytes for seat in self.seats)
        order = scale_order(
            stored_bytes=stored,
            available_bytes=self.available_bytes,
            cpu_count=self.cpu_count,
            engines=engines,
            busy=busy_now,
            waiting=waiting,
        )
        while order.action == "add_engine" and len(self.seats) < order.engines:
            self.open_seat(_place(self.cpu_count, len(self.seats) + 1))
        return order

    def open_seat(self, place: str, *, host: str | None = None) -> Seat:
        with self._lock:
            seat = Seat(
                id=f"engine-{len(self.seats)}",
                place=place,
                host=host or (self.host if place == "this_server" else "unassigned"),
            )
            self.seats.append(seat)
            return seat

    def publish_chunk(self, chunk_id: str, text: str, *, seat_id: str | None = None) -> ChorusFrame:
        """Account the chunk on a seat and send it across the fabric."""
        with self._lock:
            seat = self._seat(seat_id) if seat_id else self._roomiest()
            foot = chunk_footprint(text)
            seat.chunks += 1
            seat.text_bytes += foot.text_bytes
            seat.stored_bytes += foot.stored_bytes
            self.catalog[chunk_id] = seat.id
            target = seat.id
            place = seat.place
        frame = self.spine.encode_frame(
            envelope_id=chunk_id,
            vector_64=[0.0] * FABRIC_WIDTH,
            hop="chunk",
            artifact_ref=chunk_id,
            metadata={
                "chunk_id": chunk_id,
                "text": text,
                "text_bytes": len((text or "").encode("utf-8")),
                "tensor_bytes": TENSOR_BYTES,
                "tensor_dim": TENSOR_DIM,
                "seat": target,
                "place": place,
            },
        )
        self.spine.deliver(frame, from_hop="engine-0", to_hop=target)
        return frame

    def receive(self, payload: dict[str, Any]) -> Optional[str]:
        """Take a fabric frame into the shared catalog. Returns the seat id."""
        self.spine.ingest_wire(payload)
        if payload.get("type") == "chorus_frame":
            meta = dict(payload.get("metadata") or {})
            chunk_id = str(meta.get("chunk_id") or payload.get("artifact_ref") or "")
            text = str(meta.get("text") or "")
            seat_id = str(meta.get("seat") or payload.get("to_hop") or "")
            if not chunk_id:
                return None
            with self._lock:
                if seat_id and not any(seat.id == seat_id for seat in self.seats):
                    self.seats.append(
                        Seat(
                            id=seat_id,
                            place=str(meta.get("place") or "other_server"),
                            host="remote",
                        )
                    )
                seat = self._seat(seat_id) if seat_id else self.seats[-1]
                if chunk_id not in self.catalog:
                    foot = chunk_footprint(text)
                    seat.chunks += 1
                    seat.text_bytes += foot.text_bytes
                    seat.stored_bytes += foot.stored_bytes
                    self.catalog[chunk_id] = seat.id
                return seat.id
        return None

    def _run_write(self, fn: Callable[[], Any]) -> Any:
        with self._turn:
            with self._lock:
                self._waiting = max(0, self._waiting - 1)
                self.seats[0].busy = True
            try:
                return fn()
            finally:
                with self._lock:
                    self.seats[0].busy = False

    def _seat(self, seat_id: str) -> Seat:
        for seat in self.seats:
            if seat.id == seat_id:
                return seat
        raise KeyError(seat_id)

    def _roomiest(self) -> Seat:
        return min(self.seats, key=lambda seat: seat.stored_bytes)


def _engines_for(stored_bytes: int, available_bytes: int) -> int:
    if available_bytes <= 0:
        return 1
    engines = 1
    while stored_bytes > engines * available_bytes:
        engines += 1
    return engines


def _place(cpu_count: int, engines: int) -> str:
    """Another engine fits on this server only when the free CPUs cover its thinker processes."""
    if engines <= 1:
        return "this_server"
    if cpu_count >= engines * ENGINE_PROCESSES:
        return "this_server"
    return "other_server"


def _pool_size(name: str, default: int) -> int:
    raw = os.environ.get(name)
    if raw is None or not raw.strip():
        return max(1, default)
    return max(1, int(raw))


_STAMP = datetime(2026, 1, 1, tzinfo=timezone.utc)


def _node_json_bytes(text: str) -> int:
    from prismcortex.models import Node

    node = Node(
        id="chunk",
        label=text,
        kind="chunk",
        embedding=[float(index) / TENSOR_DIM for index in range(TENSOR_DIM)],
        attributes={},
        created_at=_STAMP,
    )
    return len(node.model_dump_json().encode("utf-8"))


def _available_bytes() -> int:
    if os.name == "nt":
        import ctypes

        class MEMORYSTATUSEX(ctypes.Structure):
            _fields_ = [
                ("dwLength", ctypes.c_ulong),
                ("dwMemoryLoad", ctypes.c_ulong),
                ("ullTotalPhys", ctypes.c_ulonglong),
                ("ullAvailPhys", ctypes.c_ulonglong),
                ("ullTotalPageFile", ctypes.c_ulonglong),
                ("ullAvailPageFile", ctypes.c_ulonglong),
                ("ullTotalVirtual", ctypes.c_ulonglong),
                ("ullAvailVirtual", ctypes.c_ulonglong),
                ("ullAvailExtendedVirtual", ctypes.c_ulonglong),
            ]

        status = MEMORYSTATUSEX()
        status.dwLength = ctypes.sizeof(MEMORYSTATUSEX)
        if not ctypes.windll.kernel32.GlobalMemoryStatusEx(ctypes.byref(status)):
            raise OSError("GlobalMemoryStatusEx failed")
        return int(status.ullAvailPhys)
    pages = os.sysconf("SC_AVPHYS_PAGES")
    width = os.sysconf("SC_PAGE_SIZE")
    return int(pages) * int(width)


def _print_report(texts: list[str]) -> None:
    budget = machine_budget()
    rows = performance_matrix(texts, available_bytes=budget.available_bytes, cpu_count=budget.cpu_count)
    last = rows[-1] if rows else None
    order = scale_order(
        stored_bytes=0 if last is None else last.stored_bytes,
        available_bytes=budget.available_bytes,
        cpu_count=budget.cpu_count,
        engines=1,
        busy=False,
        waiting=0,
    )
    print(f"cpus {budget.cpu_count}")
    print(f"available_bytes {budget.available_bytes}")
    print(f"tensor_bytes {TENSOR_BYTES}")
    print(f"thinker_heads {THINKER_HEADS}")
    print("chunks text_bytes tensor_bytes stored_bytes engines thinker_processes place")
    for row in rows:
        print(
            f"{row.chunks} {row.text_bytes} {row.tensor_bytes} {row.stored_bytes} "
            f"{row.engines} {row.thinker_processes} {row.place}"
        )
    print(f"action {order.action}")
    print(f"place {order.place}")
    print(f"reason {order.reason}")


def main(argv: list[str] | None = None) -> None:
    """Print the matrix for chunk texts, or for N copies of a sample byte length."""
    parser = argparse.ArgumentParser(description="Show memory and CPU for a set of chunks.")
    parser.add_argument("path", nargs="?", help="UTF-8 file. Blank lines separate chunks.")
    parser.add_argument("--chunks", type=int, default=0, help="How many sample chunks, when no file is given.")
    parser.add_argument("--bytes", type=int, default=400, help="UTF-8 size of each sample chunk.")
    args = parser.parse_args(argv)
    if args.path:
        raw = open(args.path, encoding="utf-8").read()
        texts = [part.strip() for part in raw.split("\n\n") if part.strip()]
    else:
        count = args.chunks if args.chunks > 0 else 1
        sample = ("x" * max(0, args.bytes)) or "x"
        texts = [sample] * count
    _print_report(texts)


if __name__ == "__main__":
    main()
