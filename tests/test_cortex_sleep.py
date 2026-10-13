"""Sleep writes lexical links in the graph and leaves stored tensors alone."""

import inspect
from pathlib import Path

import numpy as np
from chorusgraph.persistence.sqlite_graph_store import SqliteGraphStore
from prismcortex.models import DeltaOp, Node, Operation, StateDelta
from vectorprism.tensor_contract import PSMTensorContract

from cpu_llm.cortex_sleep import CortexSleepConsolidator
from cpu_llm.ir.schema import EIRProposition, EpistemicStatus, Modality, Polarity, TypedEntity, TypedPredicate
from cpu_llm.pipeline import Appliance, _remember_chunk
from cpu_llm.taxonomy import IngestTaxonomyIndexer


def _relation() -> np.ndarray:
    width = PSMTensorContract.RELATIONAL.length
    return np.linspace(0.2, 1.0, width, dtype=np.float32)


def _tensor(sign: float = 1.0) -> np.ndarray:
    vector = np.zeros(PSMTensorContract.TOTAL_DIM, dtype=np.float32)
    dense = PSMTensorContract.DENSE_CORE
    vector[dense.start] = 1.0
    relation = PSMTensorContract.RELATIONAL
    vector[relation.start : relation.end] = sign * _relation()
    return vector


def _claim(proposition_id: str, polarity: Polarity) -> EIRProposition:
    return EIRProposition(
        proposition_id=proposition_id,
        polarity=polarity,
        modality=Modality.DECLARATIVE,
        subject=TypedEntity(raw_text="peat", lemma="peat", is_plural=False),
        predicate=TypedPredicate(lemma="cover"),
        object_target=TypedEntity(raw_text="island", lemma="island", is_plural=False),
        epistemic_status=EpistemicStatus.RETRIEVED_FACT,
        epistemic_weight=1.0,
    )


def _tags(category: str = "papa-stour") -> list[dict[str, object]]:
    return [
        {
            "term": "peat",
            "category": category,
            "resonance_key": f"{category}:peat",
            "channel_index": PSMTensorContract.DENSE_CORE.start,
        }
    ]


def _store(tmp_path: Path) -> SqliteGraphStore:
    return SqliteGraphStore(tmp_path / "graph.db", tenant_id="sleep-test")


def _put(
    store: SqliteGraphStore,
    node_id: str,
    label: str,
    tensor: np.ndarray,
    *,
    category: str = "papa-stour",
    proposition: EIRProposition | None = None,
) -> None:
    attributes: dict[str, object] = {"taxonomy_tags": _tags(category), "related_terms": []}
    if proposition is not None:
        attributes["proposition"] = proposition.model_dump(mode="json")
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
                        attributes=attributes,
                    ),
                    reason="fixture",
                )
            ]
        )
    )


def _by_id(store: SqliteGraphStore, node_id: str) -> Node:
    return next(node for node in store.all_nodes() if node.id == node_id)


class _Resonance:
    def __init__(self) -> None:
        self.ingested: list[str] = []
        self.amplitude: np.ndarray | None = None
        self.group_id: str | None = None
        self.pairs: list[tuple[str, str]] = []

    def ingest(self, chunk_id, amplitude, frequency=None, parent_id=None, group_id=None):
        self.ingested.append(chunk_id)
        self.amplitude = np.asarray(amplitude, dtype=np.float32)
        self.group_id = group_id

    def record_co_activation(self, tag, document_id):
        self.pairs.append((tag, document_id))


def test_index_chunks_keeps_tags_beside_the_proposition(tmp_path: Path):
    assert "_taxonomy_indexer" in inspect.getsource(Appliance.index_chunks)
    assert "build_chunk_tags" in inspect.getsource(Appliance.index_chunks)
    assert "build_chunk_tags" in inspect.getsource(Appliance.catalog_chunks)
    text = "There is no peat because the volcanic rocks do not hold it."
    document_id = "wikitext2-papa-stour-p0007"
    tensor = _tensor()
    resonance = _Resonance()
    tags = IngestTaxonomyIndexer(resonance).build_chunk_tags(document_id, text, tensor)
    peat = next(tag for tag in tags if tag.term == "peat")
    assert peat.category == "papa-stour"
    assert peat.resonance_key == "papa-stour:peat"
    assert peat.channel_index == PSMTensorContract.DENSE_CORE.start
    assert "papa-stour:peat" in resonance.ingested
    assert resonance.group_id == "papa-stour"
    assert (peat.resonance_key, document_id) in resonance.pairs
    dense = PSMTensorContract.DENSE_CORE
    amplitude = resonance.amplitude
    assert amplitude is not None
    assert float(np.linalg.norm(amplitude[dense.start : dense.end])) == 1.0
    assert float(np.max(np.abs(amplitude[: dense.start]))) == 0.0
    assert float(np.max(np.abs(amplitude[dense.end :]))) == 0.0
    proposition = _claim("peat-present", Polarity.AFFIRMATIVE)
    store = _store(tmp_path)
    _remember_chunk(store, document_id, text, tensor, proposition, tags)
    node = _by_id(store, document_id)
    assert node.attributes["proposition"]["proposition_id"] == "peat-present"
    stored = {item["term"]: item["resonance_key"] for item in node.attributes["taxonomy_tags"]}
    assert stored["peat"] == "papa-stour:peat"
    assert node.embedding == [float(value) for value in tensor]


def test_sleep_writes_bidirectional_terms_and_keeps_the_embedding(tmp_path: Path):
    store = _store(tmp_path)
    left = _tensor()
    right = _tensor()
    _put(store, "a", "peat paragraph", left)
    _put(store, "b", "volcanic paragraph", right)
    before = {node.id: list(node.embedding or []) for node in store.all_nodes()}
    formed = CortexSleepConsolidator(store).run_sleep_cycle()
    assert formed == 1
    node_a = _by_id(store, "a")
    node_b = _by_id(store, "b")
    assert node_a.embedding == before["a"]
    assert node_b.embedding == before["b"]
    assert "volcanic paragraph" in node_a.attributes["related_terms"]
    assert "peat paragraph" in node_b.attributes["related_terms"]
    links = [edge for edge in store.all_edges() if edge.relation == "TAXONOMIC_LINK" and edge.is_current]
    assert len(links) == 1
    assert {links[0].src, links[0].dst} == {"a", "b"}
    assert CortexSleepConsolidator(store).run_sleep_cycle() == 0


def test_opposing_relational_polarity_does_not_merge(tmp_path: Path):
    store = _store(tmp_path)
    _put(store, "a", "peat paragraph", _tensor(1.0))
    _put(store, "b", "opposing paragraph", _tensor(-1.0))
    assert CortexSleepConsolidator(store).run_sleep_cycle() == 0
    assert _by_id(store, "a").attributes["related_terms"] == []
    assert store.all_edges() == []


def test_contradiction_ruin_blocks_the_link(tmp_path: Path):
    store = _store(tmp_path)
    _put(store, "a", "peat covers the island", _tensor(), proposition=_claim("yes", Polarity.AFFIRMATIVE))
    _put(store, "b", "peat does not cover the island", _tensor(), proposition=_claim("no", Polarity.NEGATIVE))
    assert CortexSleepConsolidator(store).run_sleep_cycle() == 0
    assert _by_id(store, "a").attributes["related_terms"] == []
    assert _by_id(store, "b").attributes["related_terms"] == []
    assert store.all_edges() == []
