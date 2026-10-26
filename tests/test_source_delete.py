"""One source can be removed from the index, the graph, and the word index."""

import json

import pytest
from chorusgraph.persistence.sqlite_graph_store import SqliteGraphStore
from prismcortex.models import DeltaOp, Edge, Node, Operation, StateDelta

from cpu_llm.retrieval import VectorPrismIndex
from cpu_llm.source_delete import delete_stored_source, source_prefix
from cpu_llm.word_taxonomy import drop_document_prefix


class _Cursor:
    def __init__(self, db):
        self.db = db

    def __enter__(self):
        return self

    def __exit__(self, *args):
        return False

    def execute(self, sql, params):
        self.db.sql = sql
        self.db.params = params
        self.rowcount = self.db.rows


class _Conn:
    def __init__(self, rows):
        self.rows = rows

    def cursor(self):
        return _Cursor(self)


class _Db:
    def __init__(self, rows):
        self.conn = _Conn(rows)


def test_a_file_name_uses_the_ingest_prefix():
    assert source_prefix("notes/harbor-field-guide.pdf") == "harbor-field-guide-pdf-p"
    assert source_prefix("harbor-field-guide-pdf-p0001") == "harbor-field-guide-pdf-p"
    assert source_prefix("notes-p") == "notes-p"
    with pytest.raises(ValueError):
        source_prefix("   ")


def test_delete_prefix_refuses_a_wildcard_before_sql():
    index = object.__new__(VectorPrismIndex)
    index.db = _Db(3)
    with pytest.raises(ValueError):
        index.delete_prefix("notes_%")
    assert not hasattr(index.db.conn, "sql")
    assert index.delete_prefix("notes-p") == 3
    assert index.db.conn.params == ("^notes-p[0-9]{4,}(-v[0-9]+)?$",)
    assert "document_id ~ %s" in index.db.conn.sql


def test_word_ids_for_that_prefix_are_dropped_and_shared_words_remain():
    index = {
        "kestrel": {"notes": ["notes-p0001", "other-p0001"]},
        "falcon": {"notes": ["notes-p0001"]},
    }
    assert drop_document_prefix(index, "notes-p") == 2
    assert index == {"kestrel": {"notes": ["other-p0001"]}}
    longer = {"policy": {"hr": ["hr-p0001", "hr-policy-p0001", "hr-p0001-v12"]}}
    assert drop_document_prefix(longer, "hr-p") == 2
    assert longer == {"policy": {"hr": ["hr-policy-p0001"]}}


def test_delete_removes_the_source_node_and_keeps_an_output_format(tmp_path):
    store = SqliteGraphStore(tmp_path / "graph.db", tenant_id="cpu-llm")
    store.apply(
        StateDelta(
            ops=[
                DeltaOp(
                    operation=Operation.ASSIMILATE,
                    node=Node(id="notes-p0001", label="The harbor kestrel is a small coastal falcon.", kind="chunk"),
                    reason="test",
                ),
                DeltaOp(
                    operation=Operation.ASSIMILATE,
                    node=Node(id="output-format:email", label="output-format:email", kind="output_format"),
                    reason="test",
                ),
                DeltaOp(
                    operation=Operation.ASSIMILATE,
                    edge=Edge(id="e1", src="notes-p0001", dst="output-format:email", relation="mentioned"),
                    reason="test",
                ),
            ]
        )
    )
    tags = {"kestrel": {"notes": ["notes-p0001"]}}
    path = tmp_path / "word_tags.json"
    index = object.__new__(VectorPrismIndex)
    index.db = _Db(1)
    receipt = delete_stored_source(index, store, tags, path, "notes")
    assert receipt["prefix"] == "notes-p"
    assert receipt["vector_rows"] == 1
    assert receipt["nodes_remaining"] == []
    assert receipt["word_ids"] == 1
    assert receipt["resonance"] == "unchanged"
    assert receipt["word_relations"] == "unchanged"
    ids = {node.id for node in store.all_nodes()}
    assert "notes-p0001" not in ids
    assert "output-format:email" in ids
    assert store.all_edges() == []
    assert json.loads(path.read_text(encoding="utf-8")) == {}
    store.close()


def test_deleting_one_source_leaves_a_longer_name(tmp_path):
    from cpu_llm.knowledge_graph import KnowledgeGraph
    from cpu_llm.source_delete import erase_graph_prefix

    store = SqliteGraphStore(tmp_path / "graph.db", tenant_id="cpu-llm")
    store.apply(
        StateDelta(
            ops=[
                DeltaOp(
                    operation=Operation.ASSIMILATE,
                    node=Node(id="hr-p0001", label="The handbook is a policy.", kind="chunk"),
                    reason="test",
                ),
                DeltaOp(
                    operation=Operation.ASSIMILATE,
                    node=Node(id="hr-policy-p0001", label="The handbook is a guide.", kind="chunk"),
                    reason="test",
                ),
            ]
        )
    )
    erase_graph_prefix(store, "hr-p")
    ids = {node.id for node in store.all_nodes()}
    assert "hr-p0001" not in ids
    assert "hr-policy-p0001" in ids
    store.close()

    graph = KnowledgeGraph(tmp_path / "facts.db")
    graph.replace(
        [
            ("hr-p0001", "The handbook is a policy."),
            ("hr-policy-p0001", "The handbook is a guide."),
        ]
    )
    graph.delete_prefix("hr-p")
    with graph._connect() as conn:
        fact_ids = {row["document_id"] for row in conn.execute("SELECT document_id FROM facts")}
    assert "hr-p0001" not in fact_ids
    assert "hr-policy-p0001" in fact_ids
