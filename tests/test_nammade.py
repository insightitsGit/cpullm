"""Nammade channel contracts, volumetric scan, and the explicit ask route."""
import math
from types import SimpleNamespace
from unittest.mock import Mock

import numpy as np
import pytest

from cpu_llm.nammade import (
    NammadeChannel4D,
    NammadeChannelEncoder,
    NammadeEquilibriumNode,
    NammadeRegime,
    ResourceBudget,
    encode_chunk,
    encode_query,
    equilibrium_radius,
    nammade_seed,
)
from cpu_llm.nammade.channel import require_kappa
from cpu_llm.nammade.store import store_spans
from cpu_llm.nammade.types import FrontierStatus
from cpu_llm.pipeline import Appliance


@pytest.mark.parametrize('prompt', ['Nammade: elephant', 'Invent a new concept from elephant',
                                  'Propose a testable hypothesis about elephant.'])
def test_research_routes_consume_grounded_inference(prompt):
    app = appliance(['The elephant is bigger than the donkey.', 'The donkey is bigger than the cat.'])
    response = app.ask(prompt)
    receipts = response['research_inference']['receipts']
    assert any(item['verdict'] == 'ENTAILED_BY_RULES' for item in receipts)
    assert response['research_methods']['inference']['proof_count'] >= 1
    assert 'inference' in response['routing']['post_stages']
    assert 'Rule inference' in response['reply']['text']


def test_density_rejects_the_open_gap_and_snaps_raw_scalars():
    with pytest.raises(ValueError, match="Zero-free"):
        NammadeChannel4D(0, 0, 0, 0.25)
    with pytest.raises(ValueError):
        NammadeChannel4D(0, 0, 0, float("nan"))
    assert NammadeChannelEncoder.enforce_zero_free(0) == 1
    assert NammadeChannelEncoder.enforce_zero_free(0.4) == 1
    assert NammadeChannelEncoder.enforce_zero_free(-0.2) == -1
    assert NammadeChannelEncoder.enforce_zero_free(12) == 12
    assert NammadeChannelEncoder.enforce_zero_free(-5) == -5
    with pytest.raises(ValueError):
        require_kappa(0)
    with pytest.raises(ValueError):
        require_kappa(-1)


def test_residual_is_the_scaled_cubic_and_only_zero_at_the_origin():
    kappa = 2.0
    query = NammadeChannel4D(0, 0, 0, -1)
    kb = np.array([[0.5, 0, 0, 12], [0, 0, 0, 4]], dtype=np.float32)
    distances, residuals, ratios, bridges = NammadeChannelEncoder.batch_volumetric_metrics(query, kb, kappa=kappa)
    expected = 0.5 + kappa * (4.0 / 3.0) * math.pi * (0.5 ** 3)
    assert distances[0] == pytest.approx(0.5, abs=1e-6)
    assert residuals[0] == pytest.approx(expected, abs=1e-5)
    assert ratios[0] == pytest.approx(0.5 / equilibrium_radius(kappa), abs=1e-5)
    assert residuals[1] == pytest.approx(0, abs=1e-6)
    assert bool(bridges[0]) is True
    assert bool(bridges[1]) is True
    assert residuals[0] > residuals[1]


def test_regime_priority_lock_wins_and_bridges_follow_the_query_sign():
    query = NammadeChannel4D(0, 0, 0, -1)
    channels = np.array(
        [
            [0, 0, 0, 12],
            [0.5, 0, 0, 12],
            [0.5, 0, 0, -10],
            [0.5, 0, 0, -5],
            [3, 3, 3, 12],
        ],
        dtype=np.float32,
    )
    metadata = [
        {"source_id": f"notes-p{i:04}", "span_text": f"span {i}", "span_hash": f"h{i}"}
        for i in range(1, 6)
    ]
    frame = NammadeEquilibriumNode({"nammade_channels": channels, "metadata": metadata}).execute(
        {"nammade_query_channel": query}
    )
    by_source = {item.source_id: item for item in frame["nammade_evaluations"]}
    assert by_source["notes-p0001"].regime is NammadeRegime.EQUILIBRIUM_LOCKED
    assert by_source["notes-p0001"].is_polarity_bridge is True
    assert by_source["notes-p0002"].regime is NammadeRegime.MATTER_INVARIANT
    assert by_source["notes-p0003"].regime is NammadeRegime.NAMMADE_FRONTIER
    assert by_source["notes-p0003"].is_polarity_bridge is False
    assert by_source["notes-p0004"].regime is NammadeRegime.DYNAMIC_CYCLE
    assert "notes-p0005" not in by_source
    assert frame["has_static_equilibrium"] is True
    assert frame["polarity_bridges_found"] == 2
    assert frame["nammade_frontier_status"] is FrontierStatus.EVIDENCE_EXHAUSTED
    assert [item.source_id for item in frame["nammade_evaluations"]] == [
        "notes-p0001", "notes-p0002", "notes-p0003", "notes-p0004",
    ]


def test_candidate_and_time_budgets_cap_the_scan(monkeypatch):
    query = NammadeChannel4D(0, 0, 0, 1)
    channels = np.array([[0.2, 0, 0, -4], [0.4, 0, 0, -4], [0.6, 0, 0, -4]], dtype=np.float32)
    metadata = [{"source_id": f"s{i}", "span_text": "x", "span_hash": str(i)} for i in range(3)]
    node = NammadeEquilibriumNode({"nammade_channels": channels, "metadata": metadata})
    capped = node.execute({"nammade_query_channel": query}, ResourceBudget(max_candidates=1))
    assert len(capped["nammade_evaluations"]) == 1
    assert capped["nammade_frontier_status"] is FrontierStatus.RESOURCE_CAPPED
    assert capped["nammade_evaluations"][0].is_polarity_bridge is True

    clock = iter([0.0, 10.0])
    monkeypatch.setattr("cpu_llm.nammade.node.time.perf_counter", lambda: next(clock))
    timed = node.execute({"nammade_query_channel": query}, ResourceBudget(cpu_budget_ms=1))
    assert timed["nammade_evaluations"] == []
    assert timed["nammade_frontier_status"] is FrontierStatus.RESOURCE_CAPPED


def test_lexical_projection_and_explicit_records_assign_the_documented_bands():
    ordinary = encode_chunk("notes-p0001", "Helios uses PostgreSQL.")
    assert ordinary.explicit is False
    assert ordinary.channel.d == 1
    assert (ordinary.channel.a, ordinary.channel.b, ordinary.channel.c) == (0, 0, 0)
    causal = encode_chunk("notes-p0002", "The lamp did not fail because the filament broke.")
    assert causal.channel.a == pytest.approx(0.5)
    assert causal.channel.b == pytest.approx(-1)
    frontier = encode_chunk("notes-p0003", "This remains an open wave.")
    assert frontier.channel.d == -10
    invariant = encode_chunk("notes-p0004", "Light speed is an invariant.")
    assert invariant.channel.d == 10
    assert invariant.is_invariant is True
    explicit = encode_chunk(
        "physics-p0001",
        'Nammade span: {"a": 0.25, "b": -0.5, "c": 1, "d": 12, "is_invariant": true, "domain_mask": ["DOMAIN_PHYSICS"]}\n'
        "Maxwell permittivity is nonzero.",
    )
    assert explicit.explicit is True
    assert explicit.span_text == "Maxwell permittivity is nonzero."
    assert explicit.channel.d == 12
    assert explicit.domain_mask == ("DOMAIN_PHYSICS",)
    with pytest.raises(ValueError, match="Zero-free"):
        encode_chunk("physics-p0002", 'Nammade span: {"a": 0, "b": 0, "c": 0, "d": 0} gap')
    query = encode_query("why light")
    assert query.d == -1


def test_store_writes_the_check_constraint_and_parameterized_upsert():
    span = encode_chunk("notes-p0001", "Helios uses PostgreSQL.")

    class Cursor:
        def __init__(self):
            self.statements = []

        def __enter__(self):
            return self

        def __exit__(self, *args):
            return None

        def execute(self, sql, params=None):
            self.statements.append((sql, params))

        def executemany(self, sql, params):
            self.statements.append((sql, list(params)))

        def fetchone(self):
            return ("ns_test",)

    class Conn:
        def __init__(self):
            self.cursor_obj = Cursor()
            self.committed = False

        def cursor(self):
            return self.cursor_obj

        def commit(self):
            self.committed = True

    conn = Conn()
    assert store_spans(conn, [span]) is True
    assert conn.committed is True
    ddl = conn.cursor_obj.statements[1][0]
    assert "CHECK (nammade_d <= -1.0 OR nammade_d >= 1.0)" in ddl
    assert '"ns_test".cpullm_kb_spans' in ddl
    insert, rows = conn.cursor_obj.statements[3]
    assert "ON CONFLICT (document_id, span_hash)" in insert
    assert rows[0][0] == "notes-p0001"
    assert rows[0][6] == 1.0


def appliance(chunks):
    app = object.__new__(Appliance)
    app.tenant_id = "test"
    app.small_talk = False
    app.guard = SimpleNamespace(check=lambda _: SimpleNamespace(decision="allow"))
    rows = [dict(document_id=f"doc-p{i:04}", chunk_text=text) for i, text in enumerate(chunks, 1)]
    app.index = SimpleNamespace(strict_source_rows=Mock(return_value=(rows, 123)))
    return app


@pytest.mark.parametrize("prompt", ["Nammade: light speed.", "Please Nammade equilibrium: light speed"])
def test_prompt_scans_spans_and_quotes_bridges_with_source_attribution(prompt):
    app = appliance([
        'Nammade span: {"a": 0, "b": 0, "c": 0, "d": 12}\nLight speed is constant.',
        "A hedged claim could change because the lamp failed.",
        'Nammade span: {"a": 0, "b": 0, "c": 0, "d": 0.2} broken',
    ])
    result = app.ask(prompt)
    receipt = result["nammade"]
    assert receipt["triggered"] is True
    assert receipt["node"] == "nammade_equilibrium"
    assert result["answer_evidence"]
    assert result["audit_passed"] is False
    assert result["answer_status"] == "nammade"
    assert receipt["has_static_equilibrium"] is True
    assert receipt["polarity_bridges_found"] == 1
    assert receipt["skipped_spans"] == 1
    assert receipt["stored"] is False
    [locked] = [item for item in receipt["evaluations"] if item["regime"] == "EQUILIBRIUM_LOCKED"]
    assert locked["span_text"] == "Light speed is constant."
    assert locked["is_polarity_bridge"] is True
    assert "Light speed is constant." in result["reply"]["text"]
    assert "do not verify a physical law" in result["reply"]["text"]
    assert result["routing"]["post_stages"] == ["nammade_equilibrium", "inference"]
    assert result['research_inference']['outcome'] == 'no_applicable_rule'


def test_other_routes_and_strict_mode_do_not_emit_a_nammade_scan():
    assert nammade_seed("What is Nammade?") is None
    assert nammade_seed("What does Helios use?") is None
    assert nammade_seed('Explain "Nammade: light".') is None
    assert nammade_seed("Do not run Nammade: light") is None
    app = appliance(["Helios uses PostgreSQL."])
    blocked = app.ask("Nammade: light", strict_evidence=True)
    assert blocked["answer_status"] == "unsupported"
    assert "nammade" not in blocked
    with pytest.raises(ValueError, match="separately"):
        app.ask("Nammade: light", invent=True)


def test_api_flag_uses_the_message_and_a_custom_stiffness():
    app = appliance(['Nammade span: {"a": 0, "b": 0, "c": 0, "d": 4}\nA measured permittivity.'])
    result = app.ask("permittivity", nammade=True, nammade_kappa=2)
    assert result["nammade"]["kappa"] == 2
    assert result["nammade"]["query_channel"]["d"] == -1
    assert result["nammade"]["evaluations"][0]["regime"] == "EQUILIBRIUM_LOCKED"


def test_dense_admission_keeps_a_far_span_and_does_not_lock_the_origin():
    query = NammadeChannel4D(0, 0, 0, -1)
    channels = np.array(
        [
            [1, 0, 0, 1],
            [0, 0, 0, -1],
            [0, 0, 0, 1],
        ],
        dtype=np.float32,
    )
    metadata = [
        {
            "source_id": "physics",
            "span_text": "Maxwell gives the wave speed.",
            "span_hash": "h1",
            "dense_gated": True,
            "force_admit": True,
            "dense_similarity": 0.80,
        },
        {
            "source_id": "hypothesis",
            "span_text": "A medium might change it.",
            "span_hash": "h2",
            "dense_gated": True,
            "force_admit": True,
            "dense_similarity": 0.91,
        },
        {
            "source_id": "water",
            "span_text": "Water boils.",
            "span_hash": "h3",
            "dense_gated": True,
            "force_admit": False,
            "dense_similarity": 0.40,
        },
    ]
    frame = NammadeEquilibriumNode({"nammade_channels": channels, "metadata": metadata}).execute(
        {"nammade_query_channel": query}
    )
    assert [item.source_id for item in frame["nammade_evaluations"]] == ["hypothesis", "physics"]
    assert frame["nammade_evaluations"][0].regime is NammadeRegime.DYNAMIC_CYCLE
    assert frame["nammade_evaluations"][0].is_polarity_bridge is False
    assert frame["nammade_evaluations"][1].is_polarity_bridge is True
    assert frame["has_static_equilibrium"] is False


def test_dense_core_labels_a_hypothesis_and_drops_an_unrelated_paragraph():
    app = appliance([
        "The speed of light in vacuum is defined as exactly 299792458 meters per second.",
        "A proposed medium might change the vacuum speed of light.",
        "The boiling point of water at standard atmospheric pressure is 100 degrees Celsius.",
    ])
    ones = np.ones(1024, dtype=np.float32)
    water = np.zeros(1024, dtype=np.float32)
    water[16] = 1.0

    def search(query, top_k=5, query_tensor=None, as_of=None):
        del query, top_k, query_tensor, as_of
        return [
            {"document_id": "doc-p0001", "tensor_1024d": ones},
            {"document_id": "doc-p0002", "tensor_1024d": ones},
            {"document_id": "doc-p0003", "tensor_1024d": water},
        ]

    app.index.encode_query = lambda query: ones
    app.index.search = search
    result = app.ask("Nammade: What constants determine the speed of light in vacuum?")
    receipt = result["nammade"]
    assert result["answer_evidence"]
    assert result["audit_passed"] is False
    by_text = {item["span_text"]: item for item in receipt["evaluations"]}
    assert "boiling point" not in result["reply"]["text"]
    assert by_text["The speed of light in vacuum is defined as exactly 299792458 meters per second."]["claim"] == "source statement"
    assert by_text["The speed of light in vacuum is defined as exactly 299792458 meters per second."]["is_polarity_bridge"] is True
    hypothesis = by_text["A proposed medium might change the vacuum speed of light."]
    assert hypothesis["claim"] == "hypothesis"
    assert hypothesis["is_polarity_bridge"] is False
    assert hypothesis["regime"] == "DYNAMIC_CYCLE"
    assert "claim=hypothesis" in receipt["diagnostics"]
    assert "do not verify a physical law" in result["reply"]["text"]

def test_scoped_scan_uses_snapshot_date_and_abstains_for_unrelated_text():
    from cpu_llm.access import CallerContext

    app = appliance(["# Equilibrium overview", "The solid sphere is blue."])
    app.index.encode_query = Mock(return_value=np.ones(1024, dtype=np.float32))
    app.index.search_allowed = Mock(return_value=[])
    app.index.search = Mock(side_effect=AssertionError("unscoped search"))
    caller = CallerContext(tenant_id=app.tenant_id, caller_id="reader", request_id="nammade-scope",
                           allowed_sources=frozenset({"doc-p"}))
    result = app.ask("Nammade: saxophone", caller=caller, as_of=123)
    assert result["answer_status"] == "insufficient_evidence"
    assert result["answer_evidence"] == []
    assert result["nammade"]["word_relations"] == []
    assert app.index.search_allowed.call_args.args[1] == caller.allowed_sources
    assert app.index.search_allowed.call_args.kwargs["as_of"] == 123

def test_treatise_stiffness_question_prefers_the_definition_over_headings():
    from pathlib import Path

    path = Path(__file__).resolve().parents[1] / "docs" / "nammade-continuum-verified-edition.md"
    chunks = path.read_text(encoding="utf-8").split("\n\n")
    result = appliance([chunk for chunk in chunks if chunk.strip()]).ask(
        "Nammade: What is the role of volumetric stiffness kappa?"
    )
    assert result["verification_scope"] == "source_attribution"
    assert "volumetric stiffness constant" in result["answer_evidence"][0]["span"]
    assert "dimensional consistency" in result["answer_evidence"][0]["span"]
    assert "Query channel:" not in result["reply"]["text"]
    assert "Query channel:" in result["nammade"]["diagnostics"]

@pytest.mark.parametrize("prompt", [
    "Propose a testable hypothesis about light speed.",
    "Generate a hypothesis about light speed.",
    "Hypothesize about light speed.",
])
def test_hypothesis_route_attaches_scan_using_the_same_snapshot(prompt):
    app = appliance(["Light speed is an invariant."])
    result = app.ask(prompt)
    assert result["invention"]["triggered"]
    assert result["nammade"]["mode"] == "research_diagnostics"
    assert result["nammade"]["evaluations"][0]["source_id"] == "doc-p0001"
    assert result["answer_status"] != "nammade"
    app.index.strict_source_rows.assert_called_once()
    assert "nammade" not in app.ask(prompt, strict_evidence=True)


def test_research_command_runs_cited_scan():
    app = appliance(["Light speed is an invariant."])
    result = app.ask("Please investigate light speed.")
    assert result["answer_status"] == "nammade"
    assert result["answer_evidence"][0]["span"] == "Light speed is an invariant."

def test_research_branches_overlap_and_return_hypothesis_options(monkeypatch):
    from threading import Barrier

    from cpu_llm import invention, research_hypotheses
    from cpu_llm.nammade import execute

    ready = Barrier(3, timeout=5)

    def synchronized(function):
        def run(*args, **kwargs):
            ready.wait()
            return function(*args, **kwargs)
        return run

    monkeypatch.setattr(invention, "_innovation_options", synchronized(invention._innovation_options))
    monkeypatch.setattr(research_hypotheses, "hypothesis_options", synchronized(research_hypotheses.hypothesis_options))
    monkeypatch.setattr(execute, "execute_nammade", synchronized(execute.execute_nammade))
    prediction = "Light speed might vary in the proposed medium."
    app = appliance([prediction])
    reply = app.ask("Propose a testable hypothesis about light speed.")
    assert reply["answer_status"] == "hypotheses"
    assert reply["routing"]["post_stages"] == [
        "taxonomy_invention", "research_hypotheses", "nammade_equilibrium", "abductive_bridge", "inference",
    ]
    assert reply["research_options"][0]["prediction"] == prediction
    assert reply["research_options"][0]["document_id"] == "doc-p0001"
    assert "H1." in reply["reply"]["text"]
    assert "Nammade comparison" in reply["reply"]["text"]
    for section in ("### Innovation", "### Hypothesis generation", "### Nammade comparison"):
        assert section in reply["reply"]["text"]
    assert reply["research_methods"]["innovation"]["outcome"] == "insufficient_evidence"
    assert reply["research_methods"]["hypothesis_generation"]["option_count"] == 1
    assert prediction in reply["reply"]["text"]
    assert reply["nammade"]["as_of"] == 123
    app.index.strict_source_rows.assert_called_once()

def test_sidm_option_joins_an_observable_and_independent_bound():
    from cpu_llm.research_hypotheses import hypothesis_options

    rows = [
        dict(document_id="review", chunk_text="SIDM simulations produce cores in dwarf galaxies with sizes of (0.3–1.5) kpc."),
        dict(document_id="merger", chunk_text=(
            "Bullet Cluster simulations with dark matter self-interactions used the mass peak and galaxy centroid. "
            "They gave an upper bound of 1.25 square centimeters per gram at 68 percent confidence."
        )),
    ]
    query = "self-interacting dark matter"
    [option] = hypothesis_options(query, rows)
    assert option["origin"] == "cross_source_synthesis"
    assert "0.3–1.5 kpc" in option["prediction"]
    assert "1.25 cm²/g" in option["test"]
    assert [p["document_id"] for p in option["premises"]] == ["review", "merger"]
    assert not hypothesis_options(query, rows[:1])
    assert not hypothesis_options("dark matter identity", rows)
