"""Sleep records the relation PrismCognition accepts between words."""

from pathlib import Path

import numpy as np
from chorusgraph.persistence.sqlite_graph_store import SqliteGraphStore
from prismcortex.models import DeltaOp, Node, Operation, StateDelta
from vectorprism.tensor_contract import PSMTensorContract

from cpu_llm.audit.entailment import EpistemicEntailmentAuditor
from cpu_llm.cognition.adapter import PrismCognitionSubspaceAdapter
from cpu_llm.consolidation.sleep import lexical_evidence
from cpu_llm.cortex_sleep import CortexSleepConsolidator
from cpu_llm.ir.schema import EIRProposition, EpistemicStatus, Modality, Polarity, TypedEntity, TypedPredicate
from cpu_llm.pipeline import _cognize
from cpu_llm.proposition_catalog import homarus_definition
from cpu_llm.realizer.surface import SemanticSurfaceRealizer


def _store(tmp_path: Path) -> SqliteGraphStore:
    return SqliteGraphStore(tmp_path / "graph.db", tenant_id="word-relations")


def _tensor(hyperbolic: float = 0.0) -> np.ndarray:
    vector = np.zeros(PSMTensorContract.TOTAL_DIM, dtype=np.float32)
    vector[PSMTensorContract.DENSE_CORE.start] = 1.0
    channel = PSMTensorContract.HYPERBOLIC
    vector[channel.start] = hyperbolic
    return vector


def _put(
    store: SqliteGraphStore,
    node_id: str,
    label: str,
    proposition: EIRProposition,
    tensor: np.ndarray,
) -> None:
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
                        attributes={
                            "proposition": proposition.model_dump(mode="json"),
                            "taxonomy_tags": [
                                {
                                    "term": "lobster",
                                    "category": "homarus-gammarus",
                                    "resonance_key": "homarus-gammarus:lobster",
                                    "channel_index": PSMTensorContract.DENSE_CORE.start,
                                }
                            ],
                            "related_terms": [],
                        },
                    ),
                    reason="fixture",
                )
            ]
        )
    )


def _class_proposition() -> EIRProposition:
    return EIRProposition(
        proposition_id="prop-clawed-lobster",
        polarity=Polarity.AFFIRMATIVE,
        modality=Modality.DECLARATIVE,
        subject=TypedEntity(raw_text="clawed lobster", lemma="clawed lobster", is_plural=False),
        predicate=TypedPredicate(lemma="be", tense="PRESENT", voice="ACTIVE"),
        object_target=TypedEntity(raw_text="a crustacean", lemma="crustacean", is_plural=False),
        epistemic_status=EpistemicStatus.RETRIEVED_FACT,
        epistemic_weight=1.0,
    )


def test_sleep_records_an_instance_and_answers_from_the_word(tmp_path: Path):
    store = _store(tmp_path)
    text = "Homarus gammarus, known as the European lobster, is a species of clawed lobster."
    tensor = _tensor()
    _put(store, "homarus", text, homarus_definition(), tensor)
    assert CortexSleepConsolidator(store).run_sleep_cycle() == 0
    link = next(
        edge
        for edge in store.all_edges()
        if edge.is_current and edge.src == "word:homarus" and edge.dst == "word:lobster"
    )
    assert link.relation == "INSTANCE_OF"
    assert link.provenance is not None
    assert link.provenance.agent_id == "prism-cognition"
    word = next(node for node in store.all_nodes() if node.id == "word:lobster")
    assert word.kind == "concept"
    assert word.embedding is None
    assert "european" in word.attributes["definitions"][0]["passage_words"]
    assert "lobster" in word.attributes["definitions"][0]["claim_words"]
    evidence = lexical_evidence(store, "What is the European lobster?")
    assert [item[0].proposition_id for item in evidence] == ["prop_homarus_gammarus_def"]
    assert lexical_evidence(store, "Why use hyperbolic embeddings?") == []

    class _Engine:
        memory = store
        cognition = PrismCognitionSubspaceAdapter()
        realizer = SemanticSurfaceRealizer()
        auditor = EpistemicEntailmentAuditor()
        _turn = {
            "propositions": [],
            "related_ids": ["other"],
            "hits": [
                {
                    "document_id": "other",
                    "chunk_text": "The water is cold tonight.",
                    "tensor_1024d": tensor,
                }
            ],
            "z_query": tensor,
        }

    result = _cognize(_Engine)({"message": "What is the European lobster?", "tenant_id": "cpu-llm"})
    sentence, _delivered = SemanticSurfaceRealizer().synthesize([homarus_definition()], [])
    assert result["cognition_status"] == "deliberated"
    assert result["answer"] == sentence
    assert result["audit_passed"] is True
    assert result["ruin_distance"] == 0.0
    blocked = _cognize(_Engine)({"message": "Why use hyperbolic embeddings?", "tenant_id": "cpu-llm"})
    assert blocked["cognition_status"] == "needs_evidence_propositions"


def test_a_contradiction_does_not_become_an_instance(tmp_path: Path):
    store = _store(tmp_path)
    tensor = _tensor()
    denied = homarus_definition().model_copy(
        update={"proposition_id": "prop-homarus-denied", "polarity": Polarity.NEGATIVE}
    )
    _put(store, "yes", "Homarus gammarus is a species of clawed lobster.", homarus_definition(), tensor)
    _put(store, "no", "Homarus gammarus is not a species of clawed lobster.", denied, tensor)
    assert CortexSleepConsolidator(store).run_sleep_cycle() == 0
    assert store.all_edges() == []
    assert lexical_evidence(store, "What is the European lobster?") == []


def test_a_chained_cone_writes_subclass(tmp_path: Path):
    store = _store(tmp_path)
    child = "Homarus gammarus, known as the European lobster, is a species of clawed lobster."
    parent = "The clawed lobster is a crustacean."
    _put(store, "child", child, homarus_definition(), _tensor(0.55))
    _put(store, "parent", parent, _class_proposition(), _tensor(0.2))
    CortexSleepConsolidator(store).run_sleep_cycle()
    subclass = [edge for edge in store.all_edges() if edge.relation == "SUBCLASS_OF" and edge.is_current]
    assert {edge.src for edge in subclass} >= {"word:lobster"}
    assert {edge.dst for edge in subclass} == {"word:crustacean"}
    assert all(edge.provenance is not None and edge.provenance.modality == "CONE" for edge in subclass)


def test_equal_cones_do_not_invent_a_subclass(tmp_path: Path):
    store = _store(tmp_path)
    _put(
        store,
        "child",
        "Homarus gammarus, known as the European lobster, is a species of clawed lobster.",
        homarus_definition(),
        _tensor(0.2),
    )
    _put(store, "parent", "The clawed lobster is a crustacean.", _class_proposition(), _tensor(0.2))
    CortexSleepConsolidator(store).run_sleep_cycle()
    assert [edge for edge in store.all_edges() if edge.relation == "SUBCLASS_OF"] == []
    assert any(edge.relation == "INSTANCE_OF" for edge in store.all_edges())
