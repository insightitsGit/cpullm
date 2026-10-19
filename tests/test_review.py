"""Checks from the October 12 design review."""

from cpu_llm.agents.discovery import run_discovery
from cpu_llm.agents.reply import compose_reply
from cpu_llm.catalog import title_slugs
from cpu_llm.manifest_spans import build_span_grammar
from cpu_llm.pipeline import (
    _after_shine,
    _descriptive_turn,
    _grammar,
    _hits_for_named_article,
    _observation_without_target,
)
from prismthinker.core.schemas import EvidenceItem, ReasoningContext


def test_a_failed_audit_is_absent_from_the_reply():
    rejected = "Supplier X passes fraud."
    state = {
        "message": "What is the filing?",
        "guard_decision": "allow",
        "related": [{"chunk_id": "a", "chunk_text": "A stored paragraph.", "score": 0.4}],
        "answer": None,
        "rejected_answer": rejected,
        "audit_passed": False,
        "delivery_blocked": "audit",
        "creative": True,
        "imagination": {"text": rejected + " An imagined scene."},
    }
    assert _after_shine(state) == "model01"
    reply = compose_reply(state)
    assert rejected not in reply["text"]
    assert "Imagined passage" not in reply["text"]
    assert "withheld" in reply["body"]


def test_a_failed_number_check_is_absent_from_the_reply():
    class _Appliance:
        _turn = {}

    appliance = _Appliance()
    index, mask = build_span_grammar([{"chunk_id": "a", "chunk_text": "The paragraph states no quantity."}])
    appliance._turn = {"span_index": index, "span_mask": mask}
    state = {
        "message": "What is the limit?",
        "guard_decision": "allow",
        "related": [{"chunk_id": "a", "chunk_text": "The paragraph states no quantity.", "score": 0.4}],
        "answer": "The limit is 10 million.",
        "creative": True,
        "imagination": {"text": "The limit is 10 million in a story."},
    }
    update = _grammar(appliance)(state)
    assert update["grammar_ok"] is False
    assert update["answer"] is None
    assert "10" in update["rejected_answer"]
    reply = compose_reply({**state, **update})
    assert "10" not in reply["text"]
    assert "Imagined passage" not in reply["text"]
    assert _after_shine({**state, **update}) == "model01"


def test_a_comparison_keeps_both_named_leads():
    leads = {
        "mount-elbert": {
            "document_id": "wikitext2-mount-elbert-p0001",
            "chunk_text": "Mount Elbert is the highest summit of the Rocky Mountains.",
            "final_score": 1.0,
        },
        "mount-everest": {
            "document_id": "wikitext2-mount-everest-p0001",
            "chunk_text": "Mount Everest is Earth's highest mountain above sea level.",
            "final_score": 1.0,
        },
    }

    class _Index:
        def lead_for_slug(self, slug):
            return leads.get(slug)

    assert "mount-elbert" in title_slugs("Compare Mount Elbert and Mount Everest")
    assert "mount-everest" in title_slugs("Compare Mount Elbert and Mount Everest")
    hits = [
        {
            "document_id": "wikitext2-mount-elbert-p0004",
            "chunk_text": "A later paragraph about Mount Elbert.",
            "final_score": 0.4,
        },
        {
            "document_id": "wikitext2-other-p0001",
            "chunk_text": "An unrelated article.",
            "final_score": 0.9,
        },
    ]
    kept = _hits_for_named_article(_Index(), "Compare Mount Elbert and Mount Everest", hits)
    assert kept is not None
    ids = [item["document_id"] for item in kept]
    assert ids[0] == "wikitext2-mount-elbert-p0001"
    assert "wikitext2-mount-everest-p0001" in ids
    assert "wikitext2-mount-elbert-p0004" in ids
    assert "wikitext2-other-p0001" not in ids


def test_discovery_records_a_gather_question_and_does_not_invent_one():
    gathered = run_discovery(
        {
            "message": "Why use hyperbolic embeddings?",
            "related": [{"chunk_id": "doc_hyper", "chunk_text": "Hyperbolic embeddings place taxonomy children near their parents."}],
            "thinker_directive": "gather",
            "gather_questions": ["no numeric threshold on hypothesis or objective"],
            "cognition_status": "needs_evidence_propositions",
        }
    )
    unknown = [item for item in gathered["information"] if item["kind"] == "unknown"]
    assert unknown == [
        {
            "kind": "unknown",
            "text": "no numeric threshold on hypothesis or objective",
            "provenance": "prismthinker",
        }
    ]
    answered = run_discovery(
        {
            "message": "What is the European lobster?",
            "related": [{"chunk_id": "lead", "chunk_text": "Homarus gammarus is a species of clawed lobster."}],
            "thinker_directive": "answer",
            "gather_questions": [],
            "cognition_status": "deliberated",
            "answer": "Homarus gammarus is a species of clawed lobster.",
            "ruin_distance": 0.0,
            "abstention_triggered": False,
        }
    )
    assert not any(item["kind"] == "unknown" for item in answered["information"])


def test_a_why_question_stays_out_of_descriptive_routing():
    context = ReasoningContext(
        query="Why use hyperbolic embeddings?",
        evidence=[
            EvidenceItem(
                id="neighbor",
                content="A numbered paragraph.",
                source="vectorprism",
                numeric_claims={"year": 1868.0},
            )
        ],
    )
    assert _observation_without_target(context) is True
    assert _descriptive_turn("Why use hyperbolic embeddings?", context) is False
    plain = ReasoningContext(
        query="What is Mount Elbert?",
        evidence=[
            EvidenceItem(
                id="height",
                content="14,433 feet.",
                source="vectorprism",
                numeric_claims={"height_ft": 14433.0},
            )
        ],
    )
    assert _descriptive_turn("What is Mount Elbert?", plain) is True
