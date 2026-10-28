"""Scorer fixtures and gold coverage. These tests do not ask the appliance."""

import tempfile
from pathlib import Path

from tools.benchmarks.request_pipeline.gold import build_cases, build_conversations, build_paragraphs, dump
from tools.benchmarks.request_pipeline.gold_fresh import BANNED, dump as dump_fresh
from tools.benchmarks.request_pipeline.run_eval import restart_process_record
from tools.benchmarks.request_pipeline.scorer import selftest


def test_scorer_fixtures_cover_the_required_failures():
    rows = selftest()
    names = {row["name"] for row in rows}
    assert {
        "complete",
        "partial",
        "wrong_entity",
        "reversed_claim",
        "alternative_proof",
        "missing_premise",
        "conflict_quote",
        "clarification_options",
        "private_marker",
        "aggregate_partial",
        "proof_exceeds_budget",
        "optional_exceeds_ceiling",
        "silent_omission",
        "binding_match",
        "binding_wrong_entity",
        "binding_wrong_relation",
        "binding_reversed_direction",
        "binding_negated_claim",
        "binding_licensed_every_join",
        "binding_every_without_membership",
        "binding_unlicensed_quantifier",
        "retrieval_only_proof",
        "missing_budget_metadata",
        "child_related_is_not_proof",
        "child_words_do_not_answer_the_parent",
        "runtime_overflow_flag_is_not_a_measurement",
    } <= names
    assert all(row["passed"] for row in rows)


def test_gold_coverage_manifest_matches_the_design_counts():
    with tempfile.TemporaryDirectory() as directory:
        manifest = dump(Path(directory))
    assert manifest["factual_paragraphs"] >= 120
    assert manifest["distractors"] == 300
    assert manifest["cases"] == 180
    assert manifest["scripts"] == 24
    assert manifest["splits"] == {"development": 120, "holdout": 60}
    assert manifest["contract"] == "request-pipeline-gold-v2"
    paragraphs, rules = build_paragraphs()
    cases = build_cases(paragraphs, rules)
    scripts = {item["id"]: item for item in build_conversations(paragraphs)}
    letter = next(case for case in cases if case["id"] == "unsupported-obs-05")
    assert letter["outcome"] == "answer"
    assert letter["adjudication"]["prior_outcome"] == "unsupported"
    middle = scripts["script-middle-dev"]["turns"][0]
    assert middle["forbidden"] == []
    assert "yellow" in middle["claims"]
    assert middle["adjudication"]["prior_forbidden"] == ["yellow"]
    cancel = scripts["script-cancel-hold"]["turns"][0]
    assert "Caldera" in cancel["claims"]
    assert cancel["forbidden"] == []
    criterion = scripts["script-criterion-dev"]["turns"][1]
    assert criterion["outcome"] == "insufficient"
    assert scripts["script-reopen-hold"]["turns"][1]["action"] == "reset_memory"
    ambiguous = scripts["script-two-clarify-dev"]["turns"][0]
    assert "Sextant" in ambiguous["prompt"] and "Azimuth" in ambiguous["prompt"]
    assert ambiguous["outcome"] == "clarification"


def test_fresh_corpus_keeps_the_counts_and_drops_known_names():
    with tempfile.TemporaryDirectory() as directory:
        manifest = dump_fresh(Path(directory))
        blob = "\n".join(path.read_text(encoding="utf-8") for path in Path(directory).glob("*.jsonl"))
    assert manifest["cases"] == 180
    assert manifest["scripts"] == 24
    assert manifest["splits"] == {"development": 120, "holdout": 60}
    assert manifest["distractors"] == 300
    assert manifest["factual_paragraphs"] >= 120
    assert manifest["contract"] == "request-pipeline-gold-v2-fresh"
    assert manifest["development_seed"] == 271029
    assert manifest["holdout_seed"] == 271030
    for name in BANNED:
        assert name not in blob


def test_restart_record_is_not_a_process_restart():
    record = restart_process_record("script-example", 2)
    assert record["verdict"]["restart_measurement"] == "unavailable"
    assert record["verdict"]["excluded_from_accuracy"] is True
    assert record["process_restart"] is False


def test_lifecycle_reopens_the_store_that_was_deleted(monkeypatch):
    from tools.benchmarks.request_pipeline import run_eval

    opened = []

    class Store:
        def __init__(self, namespace):
            self.namespace = namespace
            self.resonance_tags_enabled = False

        def catalog_chunks(self, chunks):
            self.chunks = list(chunks)

        def correct(self, *args, **kwargs):
            return {"status": "corrected"}

        def delete_source(self, source):
            return {"deleted": source}

    def fake_open(namespace, resonance, clock):
        opened.append((namespace, resonance, clock))
        return Store(namespace)

    def fake_ask(app, prompt, case, session_id, as_of):
        assert prompt == "What is the scratch tag?"
        assert app.namespace == original.namespace
        return ({"answer": "The retrieved passages do not settle that."}, [], 0.0)

    monkeypatch.setattr(run_eval, "_open", fake_open)
    monkeypatch.setattr(run_eval, "_ask", fake_ask)
    original = Store("scale1000_271027_dense")
    report = run_eval._lifecycle(original, "scale1000-271027-dense", clock=None)
    assert opened == [("scale1000_271027_dense", False, None)]
    assert report["namespace"] == original.namespace
    assert report["reopened_namespace"] == original.namespace
    assert report["retired_absent"] is True
    assert report["reopened_namespace"] != "scale1000-271027-dense"[:24] + "re"
