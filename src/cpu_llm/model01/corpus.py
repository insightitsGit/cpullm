"""Store checker-approved Model01 pairs in Postgres.

A row is kept only when the realizer verifies the sentence and every content
word is copied from the stored paragraph, or is one of the fixed ranking
sentences. The test split is stored and marked so a later fit can leave it
out. This module writes no weights.
"""

from __future__ import annotations

import hashlib
import os
import re
from dataclasses import dataclass

from cpu_llm.model01.generator import MODEL_ID
from cpu_llm.ranking import ranking_notice
from cpu_llm.realizer.constructions import _question_for, bundle_from_chunks
from cpu_llm.realizer.ranker import realize
from cpu_llm.retrieval import LOCAL_PG_DSN

TABLE = "model01_training_pair"
_WORD = re.compile(r"[A-Za-z][A-Za-z'-]{3,}")
_FIXED = (
    "Ranking:",
    "The sentence above states the stored ranking.",
    "The retrieved passages do not state a ranking. The sentence above is what they do state.",
    "No passage was retrieved, so no ranking is stored for this question.",
)
_RANK_WORD = frozenset(
    """
    best worst better worse highest lowest finest greatest superior inferior
    rank ranks ranked ranking outrank outranks outranked
    """.split()
)


@dataclass(frozen=True)
class TrainingPair:
    pair_id: str
    model_id: str
    split: str
    document_id: str
    kind: str
    prompt: str
    source_text: str
    gold_text: str
    construction_ids: tuple[str, ...]


@dataclass(frozen=True)
class CorpusReport:
    model_id: str
    saved: int
    by_kind: dict[str, int]
    by_split: dict[str, int]
    paragraphs: int
    checkpoint_written: bool


def prepare(dsn: str | None = None) -> CorpusReport:
    """Collect the shipped pairs and replace this model's rows."""
    rows = shipped_rows()
    pairs = collect_pairs(rows)
    save_pairs(pairs, dsn)
    return _report(pairs, paragraphs=len(rows))


def collect_pairs(rows: list[tuple[str, str, str]]) -> list[TrainingPair]:
    """One verified sentence per prompt. A paragraph that does not round-trip is dropped."""
    pairs: list[TrainingPair] = []
    for document_id, text, split in rows:
        source = str(text or "").strip()
        if not document_id or not source:
            continue
        bundle = bundle_from_chunks([(document_id, source)])
        pairs.extend(_proposition_pairs(bundle, document_id, source, split))
        pairs.extend(_frame_pairs(bundle, document_id, source, split))
        pairs.extend(_ranking_pairs(bundle, document_id, source, split))
    unique: dict[str, TrainingPair] = {}
    for pair in pairs:
        unique.setdefault(pair.pair_id, pair)
    return list(unique.values())


def save_pairs(pairs: list[TrainingPair], dsn: str | None = None) -> int:
    """Replace rows for the model ids in ``pairs``. Returns the number written."""
    import psycopg

    target = dsn or os.environ.get('VECTORPRISM_PG_DSN') or LOCAL_PG_DSN
    model_ids = sorted({pair.model_id for pair in pairs})
    with psycopg.connect(target) as conn:
        with conn.cursor() as cursor:
            cursor.execute(
                f"""
                CREATE TABLE IF NOT EXISTS {TABLE} (
                    pair_id text PRIMARY KEY,
                    model_id text NOT NULL,
                    split text NOT NULL,
                    document_id text NOT NULL,
                    kind text NOT NULL,
                    prompt text NOT NULL,
                    source_text text NOT NULL,
                    gold_text text NOT NULL,
                    construction_ids text[] NOT NULL,
                    verified boolean NOT NULL
                )
                """
            )
            if model_ids:
                cursor.execute(f"DELETE FROM {TABLE} WHERE model_id = ANY(%s)", (model_ids,))
            cursor.executemany(
                f"""
                INSERT INTO {TABLE} (
                    pair_id, model_id, split, document_id, kind, prompt,
                    source_text, gold_text, construction_ids, verified
                ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, TRUE)
                """,
                [
                    (
                        pair.pair_id,
                        pair.model_id,
                        pair.split,
                        pair.document_id,
                        pair.kind,
                        pair.prompt,
                        pair.source_text,
                        pair.gold_text,
                        list(pair.construction_ids),
                    )
                    for pair in pairs
                ],
            )
        conn.commit()
    return len(pairs)


def load_pairs(split: str | None = None, dsn: str | None = None, model_id: str = MODEL_ID) -> list[TrainingPair]:
    """Read stored pairs. ``split`` None returns every split for ``model_id``."""
    import psycopg

    target = dsn or os.environ.get('VECTORPRISM_PG_DSN') or LOCAL_PG_DSN
    query = f"""
        SELECT pair_id, model_id, split, document_id, kind, prompt, source_text, gold_text, construction_ids
        FROM {TABLE}
        WHERE model_id = %s
    """
    params: list[object] = [model_id]
    if split is not None:
        query += " AND split = %s"
        params.append(split)
    query += " ORDER BY pair_id"
    with psycopg.connect(target) as conn:
        with conn.cursor() as cursor:
            cursor.execute(query, params)
            found = cursor.fetchall()
    return [
        TrainingPair(
            pair_id=row[0],
            model_id=row[1],
            split=row[2],
            document_id=row[3],
            kind=row[4],
            prompt=row[5],
            source_text=row[6],
            gold_text=row[7],
            construction_ids=tuple(row[8] or ()),
        )
        for row in found
    ]


def shipped_rows() -> list[tuple[str, str, str]]:
    """Document id, paragraph, and split for the shipped sources."""
    from cpu_llm.source import finance_chunks, test_path, textbook_chunks, validation_path, wikitext_chunks

    rows: list[tuple[str, str, str]] = []
    groups = (
        (wikitext_chunks(validation_path(), prefix="wikitext2"), "validation"),
        (wikitext_chunks(test_path(), prefix="wikitext2test"), "test"),
        (textbook_chunks(), "textbook"),
        (finance_chunks(), "finance"),
    )
    for chunks, split in groups:
        for document_id, _title, text in chunks:
            rows.append((document_id, text, split))
    return rows


def _proposition_pairs(bundle, document_id: str, source: str, split: str) -> list[TrainingPair]:
    record = next((item for item in bundle.records if item.kind == "proposition" and item.proposition), None)
    if record is None or record.proposition is None:
        return []
    subject = record.proposition.subject.raw_text.strip()
    if not subject or subject not in source:
        return []
    prompt = f"What is {subject}?"
    return _keep(bundle, document_id, source, split, "proposition", prompt, required=subject)


def _frame_pairs(bundle, document_id: str, source: str, split: str) -> list[TrainingPair]:
    frame = next((item.frame for item in bundle.records if item.kind == "frame" and item.frame), None)
    if frame is None:
        return []
    pairs: list[TrainingPair] = []
    for kind in ("past_color", "past_location", "past_agent"):
        prompt = _question_for(kind, frame)
        pairs.extend(_keep(bundle, document_id, source, split, "frame", prompt))
    return pairs


def _ranking_pairs(bundle, document_id: str, source: str, split: str) -> list[TrainingPair]:
    notice = ranking_notice("best", [source])
    if notice is None or notice["status"] != "stated":
        return []
    pairs: list[TrainingPair] = []
    for sentence in notice["sentences"]:
        topic = _topic_word(sentence)
        if topic is None:
            continue
        prompt = f"What is the best {topic}?"
        pairs.extend(_keep(bundle, document_id, source, split, "ranking", prompt, required=sentence))
    return pairs


def _keep(
    bundle,
    document_id: str,
    source: str,
    split: str,
    kind: str,
    prompt: str,
    required: str = "",
) -> list[TrainingPair]:
    outcome = realize(bundle, prompt)
    gold = str(outcome.get("text") or "").strip()
    if outcome.get("verified") is not True or outcome.get("status") != "answered" or not gold:
        return []
    if required and required not in gold:
        return []
    if not _grounded(gold, source):
        return []
    return [
        TrainingPair(
            pair_id=_pair_id(document_id, kind, prompt, source),
            model_id=MODEL_ID,
            split=split,
            document_id=document_id,
            kind=kind,
            prompt=prompt,
            source_text=source,
            gold_text=gold,
            construction_ids=tuple(outcome.get("construction_ids") or ()),
        )
    ]


def _grounded(gold: str, source: str) -> bool:
    remainder = gold
    for phrase in _FIXED:
        remainder = remainder.replace(phrase, " ")
    folded = source.casefold()
    return all(token.casefold() in folded for token in _WORD.findall(remainder))


def _topic_word(sentence: str) -> str | None:
    for token in _WORD.findall(sentence):
        word = token.casefold()
        if word in _RANK_WORD:
            continue
        return token
    return None


def _pair_id(document_id: str, kind: str, prompt: str, source: str) -> str:
    raw = "\n".join((MODEL_ID, document_id, kind, prompt, source))
    return hashlib.sha256(raw.encode()).hexdigest()[:24]


def _report(pairs: list[TrainingPair], *, paragraphs: int) -> CorpusReport:
    by_kind: dict[str, int] = {}
    by_split: dict[str, int] = {}
    for pair in pairs:
        by_kind[pair.kind] = by_kind.get(pair.kind, 0) + 1
        by_split[pair.split] = by_split.get(pair.split, 0) + 1
    return CorpusReport(
        model_id=MODEL_ID,
        saved=len(pairs),
        by_kind=by_kind,
        by_split=by_split,
        paragraphs=paragraphs,
        checkpoint_written=False,
    )
