"""Semantic format trigger, cached in the ChorusGraph database.

An exact "write an email" still matches the format name. A paraphrase does
not. This layer asks the frozen retrieval encoder which of two readings is
closer: "Write an email about the late shipment." or "What is the late
shipment?" The same words are in both readings, so the gap is the request
itself.

Measured on all-mpnet-base-v2, the encoder already loaded for retrieval:

* "Put together an email about the late shipment." beat the question by 0.289.
* "Whip up a short essay regarding the docking delay." beat the question by 0.241.
* "What is an email?" lost by 0.707.
* "I need a writeup on the late shipment." never cleared 0.032, so it does not
  pick a format.

The margin is 0.15, below the paraphrases that named a format and above the
ones that did not. A decision is stored in the ChorusGraph sqlite file. The
next copy of that request does not encode again. Format nodes still have no
embedding, and this cache is not part of passage search.
"""

from __future__ import annotations

import hashlib
import sqlite3
from typing import Any, Callable, Optional

import numpy as np

from cpu_llm.formats import DraftOrder, OutputFormat, _asks_for, mentioned_format

SENSE_VERSION = "1"
SENSE_MARGIN = 0.15
Encode = Callable[[list[str]], Any]


class FormatSense:
    """Compare a request with an order reading and a question reading."""

    def __init__(self, store: Any, encode: Encode) -> None:
        self.store = store
        self.encode = encode
        self._memory: dict[str, Optional[DraftOrder]] = {}
        self._ensure_table()

    def classify(self, message: str) -> Optional[DraftOrder]:
        """The format and topic, or nothing when the request is not an order."""
        key = _key(message)
        cached = self._read(key)
        if cached is not _MISS:
            return cached
        order, gap = self._match(message or "")
        self._write(key, order, gap)
        return order

    def _match(self, message: str) -> tuple[Optional[DraftOrder], float]:
        mentioned = mentioned_format(message)
        if mentioned is None:
            return None, 0.0
        fmt, topic = mentioned
        return self._choose(message, topic, [fmt])

    def _choose(self, message: str, topic: str, formats: list[OutputFormat]) -> tuple[Optional[DraftOrder], float]:
        question = _question(message, topic)
        orders = [_order(fmt, topic) for fmt in formats]
        vectors = _unit(self.encode([message, question, *orders]))
        if vectors.shape[0] != 2 + len(formats):
            return None, 0.0
        message_row = vectors[0]
        question_score = float(message_row @ vectors[1])
        best: tuple[float, OutputFormat] | None = None
        for index, fmt in enumerate(formats):
            gap = float(message_row @ vectors[index + 2]) - question_score
            if best is None or gap > best[0]:
                best = (gap, fmt)
        if best is None or best[0] < SENSE_MARGIN:
            return None, 0.0 if best is None else best[0]
        return DraftOrder(best[1].id, topic), best[0]

    def _ensure_table(self) -> None:
        conn, _tenant = _connection(self.store)
        if conn is None:
            return
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS format_sense_cache (
                tenant_id TEXT NOT NULL,
                message_key TEXT NOT NULL,
                format_id TEXT NOT NULL,
                topic TEXT NOT NULL,
                gap REAL NOT NULL,
                PRIMARY KEY (tenant_id, message_key)
            )
            """
        )
        conn.commit()

    def _read(self, key: str) -> Optional[DraftOrder] | object:
        if key in self._memory:
            return self._memory[key]
        conn, tenant = _connection(self.store)
        if conn is None:
            return _MISS
        row = conn.execute(
            "SELECT format_id, topic FROM format_sense_cache WHERE tenant_id = ? AND message_key = ?",
            (tenant, key),
        ).fetchone()
        if row is None:
            return _MISS
        order = DraftOrder(row[0], row[1]) if row[0] else None
        self._memory[key] = order
        return order

    def _write(self, key: str, order: Optional[DraftOrder], gap: float) -> None:
        self._memory[key] = order
        conn, tenant = _connection(self.store)
        if conn is None:
            return
        conn.execute(
            """
            INSERT INTO format_sense_cache (tenant_id, message_key, format_id, topic, gap)
            VALUES (?, ?, ?, ?, ?)
            ON CONFLICT(tenant_id, message_key) DO UPDATE SET
                format_id = excluded.format_id,
                topic = excluded.topic,
                gap = excluded.gap
            """,
            (tenant, key, "" if order is None else order.format_id or "", "" if order is None else order.topic, float(gap)),
        )
        conn.commit()


class _Miss:
    """A cache miss. None is a cached decision that this is not a document order."""


_MISS = _Miss()


def semantic_reason(order: DraftOrder) -> str:
    """Why the semantic layer accepted this request."""
    if not order.format_id:
        return "the prompt is semantically a document order and does not name an output format"
    return f"the prompt is semantically closest to {_asks_for(order.format_id)}"


def _order(fmt: OutputFormat, topic: str) -> str:
    name = _asks_for(fmt.id)
    if topic:
        return f"Write {name} about {topic}."
    return f"Write {name}."


def _question(message: str, topic: str) -> str:
    if topic:
        return f"What is {topic}?"
    return message.strip() or "What is this?"


def _unit(raw: Any) -> np.ndarray:
    if hasattr(raw, "detach"):
        raw = raw.detach().cpu().numpy()
    matrix = np.asarray(raw, dtype=np.float64)
    if matrix.ndim == 1:
        matrix = matrix.reshape(1, -1)
    norms = np.linalg.norm(matrix, axis=1, keepdims=True)
    norms[norms == 0.0] = 1.0
    return matrix / norms


def _key(message: str) -> str:
    text = " ".join((message or "").casefold().split())
    return hashlib.sha256(f"{SENSE_VERSION}\n{text}".encode("utf-8")).hexdigest()


def _connection(store: Any) -> tuple[sqlite3.Connection | None, str]:
    conn = getattr(store, "_conn", None)
    tenant = str(getattr(store, "_tenant_id", "cpu-llm"))
    return conn, tenant
