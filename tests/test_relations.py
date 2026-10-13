"""Second- and third-hand words from the PrismRAG edge walk."""

from pathlib import Path

import numpy as np
from prismrag_patch import PrismRAG
from prismrag_patch.store.types import GraphEdge
from vectorprism.tensor_contract import PSMTensorContract

from cpu_llm.cortex_sleep import CortexSleepConsolidator
from cpu_llm.relations import (
    apply_relation_signature,
    creation_relations,
    edges_from_passages,
    relation_hands,
)
from chorusgraph.persistence.sqlite_graph_store import SqliteGraphStore
from prismcortex.models import DeltaOp, Node, Operation, StateDelta


def test_prismrag_edges_are_the_first_hand():
    rag = PrismRAG(
        mapping={
            "categories": [{"slug": "island", "label": "island"}],
            "rules": [
                {"word": "peat", "category_slug": "island"},
                {"word": "volcanic", "category_slug": "island"},
                {"word": "rock", "category_slug": "island"},
            ],
        },
        tenant_id="hands",
    )
    rag.ingest(
        records=[
            {"word": word, "text": word, "category_hint": "island"}
            for word in ("peat", "volcanic", "rock")
        ]
    )
    mapping_id = rag.store.latest_mapping(rag.tenant_id)
    edges = rag.store.get_edges(rag.tenant_id, mapping_id)
    assert edges
    assert all(isinstance(edge, GraphEdge) for edge in edges)
    hands = relation_hands(edges, ["peat"])
    assert "volcanic" in hands[1]
    assert "rock" in hands[1]
    assert hands[2] == []
    assert hands[3] == []


def test_third_hand_crosses_two_paragraphs():
    chunks = [
        ("a", "Peat covers the volcanic rock."),
        ("b", "Volcanic islands hold basalt."),
        ("c", "Basalt columns stand inland."),
    ]
    edges = edges_from_passages(chunks)
    hands = relation_hands(edges, ["peat"])
    assert "volcanic" in hands[1]
    assert "basalt" in hands[2]
    assert "columns" in hands[3]
    blocked = edges_from_passages(chunks, base_counts={"volcanic": 40, "basalt": 40})
    blocked_hands = relation_hands(blocked, ["peat"])
    assert "basalt" not in blocked_hands[2]


def test_signature_stays_in_the_relational_tail():
    dense = PSMTensorContract.DENSE_CORE
    relation = PSMTensorContract.RELATIONAL
    tensor = np.zeros(1024, dtype=np.float32)
    tensor[dense.start] = 1.0
    tensor[relation.start] = np.float32(0.25)
    signed = apply_relation_signature(
        tensor,
        {1: ["volcanic"], 2: ["basalt"], 3: ["columns"]},
    )
    assert signed[dense.start] == 1.0
    assert signed[relation.start] == np.float32(0.25)
    tail = signed[relation.end - 32 : relation.end]
    assert tail.shape == (32,)
    assert abs(float(np.linalg.norm(tail)) - 0.05) < 1e-5
    untouched = apply_relation_signature(tensor, {1: [], 2: [], 3: []})
    assert np.array_equal(untouched, tensor)


def test_creation_names_the_second_and_third_paragraphs():
    chunks = [
        ("a", "Peat covers the volcanic rock."),
        ("b", "Volcanic islands hold basalt."),
        ("c", "Basalt columns stand inland."),
    ]
    edges = edges_from_passages(chunks)
    tags = {
        "basalt": {"islands": ["b"]},
        "columns": {"stone": ["c"]},
    }
    hands, chosen = creation_relations(edges, tags, "Where does peat sit?", {"a"})
    assert "basalt" in hands[2]
    assert any(document_id == "c" and hand == 3 for hand, document_id, _word in chosen)


def _tensor() -> np.ndarray:
    vector = np.zeros(1024, dtype=np.float32)
    dense = PSMTensorContract.DENSE_CORE
    relation = PSMTensorContract.RELATIONAL
    vector[dense.start] = 1.0
    vector[relation.start : relation.end] = np.linspace(0.2, 1.0, relation.length, dtype=np.float32)
    return vector


def _store(tmp_path: Path) -> SqliteGraphStore:
    return SqliteGraphStore(tmp_path / "graph.db", tenant_id="sleep-test")


def _put(store: SqliteGraphStore, node_id: str, label: str, tensor: np.ndarray) -> None:
    store.apply(
        StateDelta(
            ops=[
                DeltaOp(
                    operation=Operation.ASSIMILATE,
                    node=Node(
                        id=node_id,
                        label=label,
                        kind="chunk",
                        embedding=[float(value) for value in tensor],
                        attributes={"taxonomy_tags": [{"category": "island"}], "related_terms": []},
                    ),
                    reason="fixture",
                )
            ]
        )
    )


class _Vectors:
    def __init__(self) -> None:
        self.rows: dict[str, np.ndarray] = {}

    def upsert(self, document_id, text, vector, meta):
        self.rows[document_id] = np.asarray(vector, dtype=np.float32)


def test_sleep_writes_the_relation_tail_and_leaves_the_dense_core(tmp_path: Path):
    store = _store(tmp_path)
    original = _tensor()
    _put(store, "a", "Peat covers the volcanic rock.", original)
    database = _Vectors()
    edges = edges_from_passages(
        [
            ("a", "Peat covers the volcanic rock."),
            ("b", "Volcanic islands hold basalt."),
        ]
    )
    CortexSleepConsolidator(store, vector_db=database, relation_edges=edges).run_sleep_cycle()
    saved = database.rows["a"]
    dense = PSMTensorContract.DENSE_CORE
    relation = PSMTensorContract.RELATIONAL
    assert saved[dense.start] == original[dense.start]
    assert saved[relation.start] == original[relation.start]
    assert abs(float(np.linalg.norm(saved[relation.end - 32 : relation.end])) - 0.05) < 1e-5
    node = next(item for item in store.all_nodes() if item.id == "a")
    assert node.embedding == [float(value) for value in original]
