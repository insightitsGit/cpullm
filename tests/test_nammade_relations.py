"""Word relations labeled by a span's Nammade channel, used only by the Nammade scan."""
from types import SimpleNamespace
from unittest.mock import Mock

from cpu_llm.nammade.encode import encode_chunk
from cpu_llm.nammade.relations import relations_for_query, relations_from_span
from cpu_llm.pipeline import Appliance


def test_polarity_of_the_span_labels_each_word_pair():
    rows = relations_from_span(encode_chunk("notes-p0001", "The lamp did not fail because the filament broke."))
    pair = {(row["left"], row["right"]): row for row in rows}[("filament", "lamp")]
    assert pair["kind"] == "contradicts"
    assert pair["a"] == 0.5
    assert pair["b"] == -1.0
    assert pair["d"] == 1.0
    assert all(row["kind"] == "contradicts" for row in rows)

    invariant = relations_from_span(encode_chunk("notes-p0002", "Light speed is an invariant."))
    speed = {(row["left"], row["right"]): row for row in invariant}[("light", "speed")]
    assert speed["kind"] == "orthogonal"
    assert speed["a"] == 0.5
    assert speed["c"] == 1.0
    assert speed["d"] == 10.0


def test_opposite_densities_make_a_polarity_bridge():
    spans = [
        encode_chunk("physics-definition-p0001", "The speed of light in vacuum is defined as exactly 299792458 meters per second."),
        encode_chunk("physics-hypothesis-p0001", "A proposed medium might change the vacuum speed of light. This hypothesis is not a measurement."),
    ]
    rows = {(row["document_id"], row["left"], row["right"]): row for row in relations_for_query(spans, ["light", "vacuum"])}
    fact = rows[("physics-definition-p0001", "light", "vacuum")]
    hypothesis = rows[("physics-hypothesis-p0001", "light", "vacuum")]
    assert fact["kind"] == "orthogonal"
    assert fact["d"] == 1.0
    assert fact["polarity_bridge"] is True
    assert hypothesis["kind"] == "contradicts"
    assert hypothesis["d"] == -1.0
    assert hypothesis["polarity_bridge"] is True


def test_scan_quotes_relations_from_the_spans_it_reads():
    text = "Light speed is an invariant."
    app = object.__new__(Appliance)
    app.tenant_id = "test"
    app.small_talk = False
    app.guard = SimpleNamespace(check=lambda _message: SimpleNamespace(decision="allow"))
    app.index = SimpleNamespace(strict_source_rows=Mock(return_value=([
        {"document_id": "notes-p0001", "chunk_text": text},
    ], 1)))
    result = app.ask("Nammade: light speed")
    assert result["answer_evidence"]
    assert result["audit_passed"] is False
    assert result["nammade"]["word_relations"][0]["kind"] == "orthogonal"
    assert "light orthogonal speed" in result["nammade"]["diagnostics"]
    assert "d=10" in result["nammade"]["diagnostics"]
    assert "do not verify a physical law" in result["reply"]["text"]
