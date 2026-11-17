# Evidence and research workspace specification

- At the public delivery boundary, emit `evidence_panel` for finalized evidence
  or a calculation receipt. Reuse cited spans, preserve role, location and
  available version/hash metadata. Provide an escaped HTML details renderer.
- Interpret explicit constant and velocity-dependent SIDM model requests.
  Record conflicts in the existing abductive receipt. Suppress automatic
  velocity-dependent test generation for constant-model prompts. Label an
  abductive mechanism that changes the requested model as an alternative.
- Emit `research_workspace` with stable per-response card IDs, origin, claim
  status, premises, technical test, missing inputs and a plain view when
  supported. Treat bound comparisons separately from executable hypotheses.
- Offer an explicit Python runner through the existing numerical evaluation
  path. Require a cited hypothesis and a caller-supplied trusted predictor,
  parameter axes, observable units and sourced limits. Preserve the existing
  scan budget and return parameter-level acceptance and failed limit IDs.
  Expose no execution of code through HTTP or prompt text.
- When PrismLexicon is enabled and a plain policy is requested, identify the
  structured plain view as preferred. Keep quotes, all technical options,
  citations and the canonical reply intact. Strict Evidence Mode keeps its
  existing response behavior.
- Regress constant versus velocity-dependent prompts, unsupported views,
  escaping, citation preservation, missing-input handling and a synthetic
  numerical scan with both accepted and rejected grid points.

## Client use

Render `result["evidence_panel"]` with
`cpu_llm.evidence_panel.render_evidence_panel` or map its sources to your own
expandable controls. Research premises are identified by option ID.

Read `result["research_workspace"]["cards"]` to display each candidate. Select
the card's `plain` view when available and preferred. Otherwise use its
`prediction` and `test`. Both views share `premises`.

Call `Appliance.run_research_test(workspace, card_id, model=..., predict=...,
axes=..., observable_units=..., limits=...)` from trusted Python application
code. The SIDM card expects a sourced independent `dwarf_fit_score` limit and
the exact cited `cluster_cross_section` upper bound in cm²/g. The merger
ceiling is exclusive. Missing inputs produce a structured response. The
runner reports accepted samples for the supplied model and grid.
