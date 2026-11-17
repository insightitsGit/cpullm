from cpu_llm.constraint_evaluator import ObservableLimit, ParameterAxis
from cpu_llm.evidence_panel import evidence_delivery, render_evidence_panel
from cpu_llm.research_hypotheses import hypothesis_options
from cpu_llm.research_workspace import research_workspace, run_research_test


def test_evidence_panel_reuses_finalized_sources_and_escapes_markup():
    evidence = {"document_id": "source", "span": "<script>example</script>", "page": 3}
    result = evidence_delivery({"answer_status": "derived_calculation",
        "answer_evidence": [evidence], "calculation": {"operation": "greater_than"}})
    panel = result["evidence_panel"]
    assert panel["sources"][0]["page"] == 3
    assert "<script>" not in render_evidence_panel(panel)
    assert "&lt;script&gt;" in render_evidence_panel(panel)
    assert result["answer_evidence"] == [evidence]
    assert "evidence_panel" not in evidence_delivery({"answer_status": "blocked", "answer_evidence": [evidence]})


def test_model_assumption_plain_view_and_explicit_scan():
    rows = [
        {"document_id": "dwarf", "chunk_text": "SIDM simulations produce cores in dwarf galaxies with sizes of (0.3-1.5) kpc."},
        {"document_id": "merger", "chunk_text": "Bullet Cluster self-interactions affect the mass peak and galaxy centroid. An upper bound of 1.25 square centimeters per gram at 68 percent confidence was reported."},
    ]
    constant = "constant-cross-section self-interacting dark matter"
    assert not hypothesis_options(constant, rows)
    assert research_workspace(constant, [], [], {})["requested_model"] == "constant_cross_section"
    query = "velocity-dependent self-interacting dark matter"
    workspace = research_workspace(query, hypothesis_options(query, rows), [], {})
    [card] = workspace["cards"]
    assert "1.25 cm²/g" in card["plain"]["test"]
    assert "68%" in card["plain"]["test"]
    assert [p["document_id"] for p in card["premises"]] == ["dwarf", "merger"]
    assert run_research_test(workspace, card["id"])["status"] == "missing_inputs"
    result = run_research_test(
        workspace, card["id"], model="synthetic", axes=[ParameterAxis("x", "1", [1, 1.25, 2])],
        predict=lambda p: {"dwarf_fit_score": p["x"], "cluster_cross_section": p["x"]},
        observable_units={"dwarf_fit_score": "1", "cluster_cross_section": "cm²/g"},
        limits=[ObservableLimit("fit", "dwarf_fit_score", "1", "synthetic data", lower=1),
                ObservableLimit("merger", "cluster_cross_section", "cm²/g", "merger", upper=1.25)],
    )
    assert result["scan"]["accepted_count"] == 1
    assert result["scan"]["points"][1]["failed_limits"] == ["merger"]
    assert result["claim_status"] == "UNVERIFIED_HYPOTHESIS"
