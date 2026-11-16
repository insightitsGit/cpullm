"""Companion table for the 4D Nammade channel.

The columns sit beside the 1024-d embedding table. They do not change that
vector's width. Density is rejected inside ``(-1, 1)`` by the table check.
"""
from __future__ import annotations

import re
from typing import Iterable

from cpu_llm.nammade.encode import EncodedSpan

_SCHEMA = re.compile(r"[A-Za-z_][A-Za-z0-9_]*")

SPANS_DDL = """
CREATE TABLE IF NOT EXISTS "{schema}".cpullm_kb_spans (
    document_id TEXT NOT NULL,
    span_hash TEXT NOT NULL,
    span_text TEXT NOT NULL,
    nammade_a FLOAT4 NOT NULL,
    nammade_b FLOAT4 NOT NULL,
    nammade_c FLOAT4 NOT NULL,
    nammade_d FLOAT4 NOT NULL,
    is_invariant BOOLEAN NOT NULL DEFAULT FALSE,
    PRIMARY KEY (document_id, span_hash),
    CHECK (nammade_d <= -1.0 OR nammade_d >= 1.0)
)
""".strip()


def store_spans(conn, spans: Iterable[EncodedSpan]) -> bool:
    """Upsert encoded spans into the connection's current schema. Return whether the write committed."""
    rows = list(spans)
    try:
        with conn.cursor() as cursor:
            cursor.execute("SELECT current_schema()")
            schema = cursor.fetchone()[0]
            if not isinstance(schema, str) or not _SCHEMA.fullmatch(schema):
                raise ValueError("current schema name is not a plain identifier")
            cursor.execute(SPANS_DDL.format(schema=schema))
            cursor.execute(
                f'CREATE INDEX IF NOT EXISTS cpullm_kb_spans_d ON "{schema}".cpullm_kb_spans (nammade_d)'
            )
            cursor.executemany(
                f'''
                INSERT INTO "{schema}".cpullm_kb_spans (
                    document_id, span_hash, span_text,
                    nammade_a, nammade_b, nammade_c, nammade_d, is_invariant
                )
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
                ON CONFLICT (document_id, span_hash) DO UPDATE SET
                    span_text = EXCLUDED.span_text,
                    nammade_a = EXCLUDED.nammade_a,
                    nammade_b = EXCLUDED.nammade_b,
                    nammade_c = EXCLUDED.nammade_c,
                    nammade_d = EXCLUDED.nammade_d,
                    is_invariant = EXCLUDED.is_invariant
                ''',
                [
                    (
                        span.source_id,
                        span.span_hash,
                        span.span_text,
                        span.channel.a,
                        span.channel.b,
                        span.channel.c,
                        span.channel.d,
                        span.is_invariant,
                    )
                    for span in rows
                ],
            )
        conn.commit()
    except Exception:
        rollback = getattr(conn, "rollback", None)
        if rollback is not None:
            try:
                rollback()
            except Exception:
                pass
        return False
    return True
