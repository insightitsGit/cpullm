"""Scorer fixtures and gold coverage. These tests do not ask the appliance."""

import tempfile
from pathlib import Path

from tools.benchmarks.request_pipeline.gold import dump
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
