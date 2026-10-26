"""Word-level resonance tags: one tag per sentence, then spreading activation.

``Appliance`` keeps this store beside ``knowledge_graph.db`` and may add its
candidates to retrieval. A recalled tag is a candidate chunk id, not an answer.

Terms used here match ``docs/resonance-tags.md``. A hub word stays in its tags
and can match a query, but it does not carry activation to another tag.
Retrieval admits a tag that shares a specific query word, or a tag spreading
reached that contains none of the query words. A tag whose only overlap is a
hub word stays out of the passage list.
"""

from __future__ import annotations

import math
import re
import sqlite3
from pathlib import Path

from cpu_llm.access import source_allowed

_TOKEN = re.compile(r"[A-Za-z]+")
_STOP = frozenset(
    """
    a an the of to and or in on for with from by at as is are was were be been being
    this that these those it its they them their he she his her we our you your not no
    nor but if then than into over under about after before between during without
    within through toward towards across above below near onto off out up down
    can may could would should will just also than while where when what which who
    how there have has had does did done doing against per via into onto
    """.split()
)


def content_words(text: str) -> list[str]:
    """Normalized content words: 3+ letters, light plural stemming, stops removed."""
    words = []
    for raw in _TOKEN.findall(text or ""):
        token = _stem(raw.casefold())
        if len(token) >= 3 and token not in _STOP:
            words.append(token)
    return words


def _stem(word: str) -> str:
    if len(word) > 4 and word.endswith("ies"):
        return word[:-3] + "y"
    if len(word) > 4 and word.endswith("es") and word[-3] in "sxz":
        return word[:-2]
    if len(word) > 3 and word.endswith("s") and not word.endswith("ss"):
        return word[:-1]
    return word


def doc_in_source(document_id: str, allowed) -> bool:
    """True when ``document_id`` is inside the caller's allowed sources.

    ``None`` is unscoped. A source prefix uses the shared paragraph boundary,
    so ``hr-p`` matches ``hr-p0001`` and not ``hr-policy-p0001``.
    """
    return source_allowed(str(document_id), allowed)


def split_sentences(text: str) -> list[str]:
    parts = re.split(r"(?<=[.!?])\s+", (text or "").strip())
    return [part.strip() for part in parts if part.strip()]


class ResonanceTags:
    """SQLite tag store for one namespace. The file sits beside ``knowledge_graph.db``."""

    def __init__(self, path: str | Path) -> None:
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        with self._connect() as conn:
            conn.executescript(
                """
                CREATE TABLE IF NOT EXISTS unit (
                    unit_id TEXT PRIMARY KEY,
                    doc_id TEXT NOT NULL,
                    ord INTEGER NOT NULL,
                    text TEXT NOT NULL
                );
                CREATE TABLE IF NOT EXISTS unit_word (
                    unit_id TEXT NOT NULL,
                    word TEXT NOT NULL,
                    tf INTEGER NOT NULL,
                    PRIMARY KEY (unit_id, word)
                );
                CREATE INDEX IF NOT EXISTS idx_unit_word_word ON unit_word(word);
                CREATE TABLE IF NOT EXISTS grp (
                    group_id INTEGER PRIMARY KEY AUTOINCREMENT
                );
                CREATE TABLE IF NOT EXISTS grp_member (
                    group_id INTEGER NOT NULL,
                    unit_id TEXT NOT NULL,
                    PRIMARY KEY (group_id, unit_id)
                );
                """
            )

    def add_chunks(self, chunks: list[tuple[str, str]], *, replace_prefix: str | None = None, consolidate: bool = False) -> int:
        """Store one tag per sentence. ``replace_prefix`` deletes that source first."""
        if replace_prefix:
            self.delete_prefix(replace_prefix)
        stored = 0
        with self._connect() as conn:
            for doc_id, text in chunks:
                self._delete_doc(conn, str(doc_id))
                for ordinal, sentence in enumerate(split_sentences(text)):
                    words = content_words(sentence)
                    if not words:
                        continue
                    unit_id = f"{doc_id}#{ordinal}"
                    conn.execute(
                        "INSERT INTO unit (unit_id, doc_id, ord, text) VALUES (?, ?, ?, ?)",
                        (unit_id, str(doc_id), ordinal, sentence),
                    )
                    counts: dict[str, int] = {}
                    for word in words:
                        counts[word] = counts.get(word, 0) + 1
                    conn.executemany(
                        "INSERT INTO unit_word (unit_id, word, tf) VALUES (?, ?, ?)",
                        [(unit_id, word, tf) for word, tf in counts.items()],
                    )
                    stored += 1
        if consolidate:
            self.consolidate()
        return stored

    def delete_prefix(self, prefix: str) -> dict[str, int]:
        """Remove tags and word rows for one source and nothing else."""
        with self._connect() as conn:
            doomed = [
                row["unit_id"]
                for row in conn.execute("SELECT unit_id, doc_id FROM unit")
                if _prefix_match(row["doc_id"], prefix)
            ]
            if not doomed:
                return {"units": 0, "words": 0}
            words = conn.execute(
                f"SELECT COUNT(*) AS n FROM unit_word WHERE unit_id IN ({','.join('?' for _ in doomed)})",
                doomed,
            ).fetchone()["n"]
            conn.execute(
                f"DELETE FROM grp_member WHERE unit_id IN ({','.join('?' for _ in doomed)})",
                doomed,
            )
            conn.execute(
                f"DELETE FROM unit_word WHERE unit_id IN ({','.join('?' for _ in doomed)})",
                doomed,
            )
            conn.execute(
                f"DELETE FROM unit WHERE unit_id IN ({','.join('?' for _ in doomed)})",
                doomed,
            )
            conn.execute("DELETE FROM grp WHERE group_id NOT IN (SELECT group_id FROM grp_member)")
            return {"units": len(doomed), "words": int(words)}

    def replace_sentence(self, document_id: str, prior_sentence: str, new_id: str, new_sentence: str) -> dict[str, int]:
        """Drop the corrected wording and store the replacement under its new id."""
        prior_keys = {_sentence_key(part) for part in split_sentences(prior_sentence)}
        prior_keys.add(_sentence_key(prior_sentence))
        prior_keys.discard("")
        removed = 0
        with self._connect() as conn:
            # Corrections are addressed by their base id even after the first
            # replacement. Retired versions must not remain retrieval candidates.
            family = re.compile(re.escape(str(document_id)) + r"(?:-v[0-9]+)?\Z")
            rows = [row for row in conn.execute("SELECT unit_id, doc_id, text FROM unit")
                    if family.fullmatch(row["doc_id"])]
            doomed = [row["unit_id"] for row in rows
                      if row['doc_id'] != str(document_id) or _sentence_key(row["text"]) in prior_keys]
            combined = " ".join(_sentence_key(row["text"]) for row in rows)
            if not doomed and rows and combined == _sentence_key(prior_sentence):
                doomed = [row["unit_id"] for row in rows]
            if doomed:
                self._delete_ids(conn, doomed)
                removed = len(doomed)
        stored = self.add_chunks([(str(new_id), new_sentence)])
        return {"removed": removed, "stored": stored}

    def counts(self) -> dict[str, int]:
        with self._connect() as conn:
            units = conn.execute("SELECT COUNT(*) AS n FROM unit").fetchone()["n"]
            words = conn.execute("SELECT COUNT(*) AS n FROM unit_word").fetchone()["n"]
            docs = conn.execute("SELECT COUNT(DISTINCT doc_id) AS n FROM unit").fetchone()["n"]
        return {"units": int(units), "words": int(words), "docs": int(docs)}

    def consolidate(self, threshold: float = 0.22) -> int:
        """Write comparison groups. Ingest leaves this off."""
        units = self._load(None)
        groups = cluster_units(units, threshold)
        with self._connect() as conn:
            conn.execute("DELETE FROM grp_member")
            conn.execute("DELETE FROM grp")
            for group in groups:
                cursor = conn.execute("INSERT INTO grp DEFAULT VALUES")
                group_id = int(cursor.lastrowid)
                conn.executemany(
                    "INSERT INTO grp_member (group_id, unit_id) VALUES (?, ?)",
                    [(group_id, unit["unit_id"]) for unit in group],
                )
        return len(groups)

    def recall_spread(self, message: str, allowed=None, decay: float = 0.5) -> dict:
        """Rank candidate tags. Ambiguous queries return senses and no units."""
        query = list(dict.fromkeys(content_words(message)))
        units = self._load(allowed)
        if not query or not units:
            return _empty()
        postings, df = _index(units)
        n = len(units)
        hubs = _hubs(df, n)
        idf = {word: math.log((n + 1) / (df.get(word, 0) + 1)) + 1.0 for word in query}
        lit: dict[str, set[str]] = {}
        for word in query:
            for unit_id in postings.get(word, ()):
                lit.setdefault(unit_id, set()).add(word)
        if not lit:
            return _empty()
        first = {unit_id: sum(idf[word] for word in found) * len(found) for unit_id, found in lit.items()}
        components = _sense_components(units, hubs)
        component_of = {unit_id: index for index, members in enumerate(components) for unit_id in members}
        corroborated = any(len(found) >= 2 for found in lit.values())
        if not corroborated:
            lit_senses = {}
            for unit_id in lit:
                lit_senses.setdefault(component_of[unit_id], []).append(unit_id)
            if len(lit_senses) >= 2:
                senses = [_sense_words(units, components[index], hubs, query) for index in lit_senses]
                senses.sort(key=lambda item: (-len(item["words"]), item["words"]))
                return {"status": "ambiguous", "units": [], "senses": senses}
        by_id = {unit["unit_id"]: unit for unit in units}
        best_id = min(first, key=lambda unit_id: (-first[unit_id], unit_id))
        chosen = set(components[component_of[best_id]])
        scores = {unit_id: float(first.get(unit_id, 0.0)) for unit_id in chosen}
        best_score = first[best_id]
        best_tags = [unit_id for unit_id in chosen if first.get(unit_id, 0.0) == best_score]
        for unit_id in best_tags:
            for word in by_id[unit_id]["words"]:
                if word in hubs:
                    continue
                for other in postings.get(word, ()):
                    if other in chosen and other != unit_id:
                        scores[other] += decay * first[unit_id]
        positive = [score for score in scores.values() if score > 0]
        floor = (min(positive) if positive else 1.0) * decay
        for unit_id in chosen:
            if scores[unit_id] <= 0:
                scores[unit_id] = floor
        ranked = sorted(chosen, key=lambda unit_id: (-scores[unit_id], unit_id))
        hits = []
        for unit_id in ranked:
            unit = by_id[unit_id]
            shared = sorted(word for word in query if word in unit["words"])
            hits.append(
                {
                    "unit_id": unit_id,
                    "doc_id": unit["doc_id"],
                    "text": unit["text"],
                    "shared": shared,
                    "expanded": not shared,
                    "score": round(scores[unit_id], 6),
                }
            )
        return {"status": "ok", "units": hits, "senses": []}

    def recall_candidates(self, message: str, allowed=None, decay: float = 0.5) -> dict:
        """The tags retrieval may load.

        ``recall_spread`` still returns every tag in the sense component, including
        one that only shares a hub such as "crane". Those hub-only tags are not
        candidates. Expanded tags stay, because they are the sentences reached
        through a specific word rather than through the ambiguous word.
        """
        result = self.recall_spread(message, allowed=allowed, decay=decay)
        if result["status"] != "ok":
            return result
        loaded = self._load(allowed)
        hubs = _hubs(_index(loaded)[1], len(loaded))
        kept = [
            unit
            for unit in result["units"]
            if unit["expanded"] or any(word not in hubs for word in unit["shared"])
        ]
        return {**result, "units": kept}

    def recall(self, message: str, allowed=None, threshold: float = 0.22) -> dict:
        """Comparison path: hard groups. Kept to show why clustering was dropped."""
        query = list(dict.fromkeys(content_words(message)))
        units = self._load(allowed)
        if not query or not units:
            return _empty()
        groups = cluster_units(units, threshold)
        ranked_groups = []
        for group in groups:
            score = 0.0
            for unit in group:
                found = [word for word in query if word in unit["words"]]
                score += len(found)
            ranked_groups.append((score, group))
        ranked_groups.sort(key=lambda item: (-item[0], item[1][0]["unit_id"]))
        if ranked_groups[0][0] <= 0:
            return _empty()
        hits = []
        for unit in sorted(ranked_groups[0][1], key=lambda item: item["unit_id"]):
            shared = sorted(word for word in query if word in unit["words"])
            hits.append(
                {
                    "unit_id": unit["unit_id"],
                    "doc_id": unit["doc_id"],
                    "text": unit["text"],
                    "shared": shared,
                    "expanded": not shared,
                    "score": float(len(shared)),
                }
            )
        return {"status": "ok", "units": hits, "senses": []}

    def lexical(self, message: str, allowed=None) -> dict:
        """Any tag that shares a query word. The strawman baseline, not a ranker."""
        query = list(dict.fromkeys(content_words(message)))
        units = self._load(allowed)
        hits = []
        for unit in units:
            shared = sorted(word for word in query if word in unit["words"])
            if not shared:
                continue
            hits.append(
                {
                    "unit_id": unit["unit_id"],
                    "doc_id": unit["doc_id"],
                    "text": unit["text"],
                    "shared": shared,
                    "expanded": False,
                    "score": float(len(shared)),
                }
            )
        hits.sort(key=lambda item: (-item["score"], item["unit_id"]))
        return {"status": "ok" if hits else "empty", "units": hits, "senses": []}

    def _load(self, allowed) -> list[dict]:
        with self._connect() as conn:
            # Capture a request-local immutable scope in this connection's UDF.
            scope = None if allowed is None else frozenset(allowed)
            conn.create_function("in_scope", 1,
                                 lambda doc_id: int(doc_in_source(doc_id, scope)), deterministic=False)
            rows = conn.execute(
                """
                SELECT unit.unit_id, unit.doc_id, unit.ord, unit.text
                FROM unit
                WHERE in_scope(unit.doc_id)
                ORDER BY unit.doc_id, unit.ord
                """
            ).fetchall()
            words = conn.execute(
                """
                SELECT unit_word.unit_id, unit_word.word
                FROM unit_word
                JOIN unit ON unit.unit_id = unit_word.unit_id
                WHERE in_scope(unit.doc_id)
                """
            ).fetchall()
        by_unit: dict[str, set[str]] = {}
        for row in words:
            by_unit.setdefault(row["unit_id"], set()).add(row["word"])
        return [
            {
                "unit_id": row["unit_id"],
                "doc_id": row["doc_id"],
                "ord": int(row["ord"]),
                "text": row["text"],
                "words": by_unit.get(row["unit_id"], set()),
            }
            for row in rows
        ]

    def _connect(self):
        conn = sqlite3.connect(self.path)
        conn.row_factory = sqlite3.Row
        return _Closing(conn)

    @staticmethod
    def _delete_ids(conn, unit_ids: list[str]) -> None:
        if not unit_ids:
            return
        marks = ",".join("?" for _ in unit_ids)
        conn.execute(f"DELETE FROM grp_member WHERE unit_id IN ({marks})", unit_ids)
        conn.execute(f"DELETE FROM unit_word WHERE unit_id IN ({marks})", unit_ids)
        conn.execute(f"DELETE FROM unit WHERE unit_id IN ({marks})", unit_ids)

    @staticmethod
    def _delete_doc(conn, doc_id: str) -> None:
        rows = [row["unit_id"] for row in conn.execute("SELECT unit_id FROM unit WHERE doc_id = ?", (doc_id,))]
        ResonanceTags._delete_ids(conn, rows)


class _Closing:
    def __init__(self, conn):
        self.conn = conn

    def __enter__(self):
        return self.conn

    def __exit__(self, exc_type, exc, tb):
        if exc_type is None:
            self.conn.commit()
        else:
            self.conn.rollback()
        self.conn.close()


def cluster_units(units: list[dict], threshold: float) -> list[list[dict]]:
    """Single-link groups. Similarity is Jaccard over every content word, hubs included."""
    parent = {unit["unit_id"]: unit["unit_id"] for unit in units}

    def find(unit_id: str) -> str:
        while parent[unit_id] != unit_id:
            parent[unit_id] = parent[parent[unit_id]]
            unit_id = parent[unit_id]
        return unit_id

    sets = {unit["unit_id"]: set(unit["words"]) for unit in units}
    ids = [unit["unit_id"] for unit in units]
    for left in range(len(ids)):
        for right in range(left + 1, len(ids)):
            if _jaccard(sets[ids[left]], sets[ids[right]]) >= threshold:
                parent[find(ids[right])] = find(ids[left])
    grouped: dict[str, list[dict]] = {}
    for unit in units:
        grouped.setdefault(find(unit["unit_id"]), []).append(unit)
    return list(grouped.values())


def _jaccard(left: set[str], right: set[str]) -> float:
    if not left and not right:
        return 0.0
    union = left | right
    if not union:
        return 0.0
    return len(left & right) / len(union)


def _index(units: list[dict]) -> tuple[dict[str, list[str]], dict[str, int]]:
    postings: dict[str, list[str]] = {}
    df: dict[str, int] = {}
    for unit in units:
        for word in unit["words"]:
            postings.setdefault(word, []).append(unit["unit_id"])
            df[word] = df.get(word, 0) + 1
    return postings, df


def _hubs(df: dict[str, int], n_tags: int) -> set[str]:
    floor = 0.15 * n_tags
    return {word for word, count in df.items() if count >= 4 and count >= floor}


def _sense_components(units: list[dict], hubs: set[str]) -> list[list[str]]:
    """Tags that share a non-hub word, closed under that link.

    A third tag that shares a non-hub word with each of two tags puts those
    two in the same component. That is the two-hop case in the design.
    Tags that contain the same non-hub word are joined directly, so the link
    follows the word index instead of comparing every tag with every other tag.
    """
    parent = {unit["unit_id"]: unit["unit_id"] for unit in units}

    def find(unit_id: str) -> str:
        while parent[unit_id] != unit_id:
            parent[unit_id] = parent[parent[unit_id]]
            unit_id = parent[unit_id]
        return unit_id

    def union(left: str, right: str) -> None:
        root_left, root_right = find(left), find(right)
        if root_left != root_right:
            parent[root_right] = root_left

    buckets: dict[str, list[str]] = {}
    for unit in units:
        for word in unit["words"]:
            if word in hubs:
                continue
            buckets.setdefault(word, []).append(unit["unit_id"])
    for members in buckets.values():
        head = members[0]
        for other in members[1:]:
            union(head, other)
    grouped: dict[str, list[str]] = {}
    for unit in units:
        grouped.setdefault(find(unit["unit_id"]), []).append(unit["unit_id"])
    return list(grouped.values())


def _sense_words(units: list[dict], member_ids: list[str], hubs: set[str], query: list[str]) -> dict:
    members = {unit["unit_id"] for unit in units if unit["unit_id"] in set(member_ids)}
    counts: dict[str, int] = {}
    for unit in units:
        if unit["unit_id"] not in members:
            continue
        for word in unit["words"]:
            if word in hubs or word in query:
                continue
            counts[word] = counts.get(word, 0) + 1
    ranked = sorted(counts, key=lambda word: (-counts[word], word))[:4]
    return {"words": ranked, "size": len(member_ids)}


def _prefix_match(document_id: str, prefix: str) -> bool:
    from cpu_llm.source_ids import matches_prefix

    return matches_prefix(document_id, prefix)


def _sentence_key(text: str) -> str:
    return " ".join(content_words(text))


def _empty() -> dict:
    return {"status": "empty", "units": [], "senses": []}
