# Quantum computing research leads

Created 2026-11-25 from a Frontier and Deepen run over 155 arXiv quant-ph papers ([review](../reviews/2026-11-25-quantum-computing/report.md), machine-readable copy: [quantum-computing-leads.json](quantum-computing-leads.json)).

**Every lead is an `UNVERIFIED_HYPOTHESIS`.** None solves an open problem. Novelty was checked only against the 155-paper knowledge base, not the wider literature. Update `status` (open, in progress, known in literature, supported, refuted) and add notes as research proceeds.

| ID | Priority | Lead | Status |
|---|---|---|---|
| [QC-1](#qc-1) | high | Do barren-plateau mitigations also remove the exponential cost of gradient-free optimizers? | partly known in literature |
| [QC-2](#qc-2) | medium | Do two barren-plateau mitigations combine (chemical initialization × mid-circuit measurements)? | open |
| [QC-3](#qc-3) | medium | How much of the cosmic-ray penalty can correlation-aware decoding recover? | open |
| [QC-4](#qc-4) | medium | Is error mitigation useful only where classical simulation is already easy? | open |
| [QC-5](#qc-5) | low | Distillation speed versus circuit error in magic-state factories | open |
| [QC-6](#qc-6) | low | Do radiation bursts correlate failures inside magic-state factories? | known in literature |

## QC-1

**Do barren-plateau mitigations also remove the exponential cost of gradient-free optimizers?** · priority high · status partly known in literature

Barren plateaus make even gradient-free optimizers scale exponentially (2011.12245). Three papers report mitigations for gradients. No paper in the knowledge base tests whether those mitigations also cut the shot cost of gradient-free optimizers.

- **Hypothesis:** mid - circuit measurements may reduce exponential scaling for gradient free optimizers through barren plateaus. (Frontier `ee1ba9bf0cbf`, topic “barren plateaus”, rank 23)
  - Scores: support 0.55, relevance 0.975, novelty 0.642
  - [arxiv-2406-14285-p0059](https://arxiv.org/abs/2406.14285): “therefore, mid-circuit measurements, circuit pretraining, entanglement regularization to add terms to the cost function, and initial partitioning play on the entanglement entropy to better mitigate barren plateaus”
  - [arxiv-2011-12245-p0037](https://arxiv.org/abs/2011.12245): “This is consistent with our main result, and demonstrates that barren plateaus can lead to exponential scaling even for gradient-free optimizers.”
  - Deepen: verdict `all_links_supported`, links ['supported', 'supported'], composition `requires_review`, knowledge-base novelty `no_overlap_found_in_snapshot`
  - Test plan (mediation): vary ['mid - circuit measurements'], measure ['exponential scaling for gradient free optimizers']. Fails if: exponential scaling for gradient free optimizers does not change when mid - circuit measurements varies with the controls fixed, or holding barren plateaus fixed leaves the effect unchanged.
- **Hypothesis:** chemical initialization may reduce exponential scaling for gradient free optimizers through barren plateaus. (Frontier `0ec63721d1ec`, topic “barren plateaus”, rank 25)
  - Scores: support 0.55, relevance 0.958, novelty 0.577
  - [arxiv-2609-22729-p0002](https://arxiv.org/abs/2609.22729): “In the benchmarks considered here, chemically initialized starting points and variational trajectories show polynomial decay of local gradient variance with system size instead of the exponential BP-like decay observed for random controls, indicating that chemical initialization mitigates barren plateaus in the local optimization regions and highlights the trainability advantage of chemically motivated VQE strategies.”
  - [arxiv-2011-12245-p0037](https://arxiv.org/abs/2011.12245): “This is consistent with our main result, and demonstrates that barren plateaus can lead to exponential scaling even for gradient-free optimizers.”
  - Deepen: not run yet
- **Hypothesis:** MPQC may reduce exponential scaling for gradient free optimizers through barren plateaus. (Frontier `7da3b79bc28e`, topic “barren plateaus”, rank 24)
  - Scores: support 0.55, relevance 0.958, novelty 0.6
  - [arxiv-2511-13408-p0002](https://arxiv.org/abs/2511.13408): “Numerical simulations demonstrate that MPQC effectively eliminates barren plateaus in PQCs for preparing thermal states of systems with up to 100 qubits and 2400 layers.”
  - [arxiv-2011-12245-p0037](https://arxiv.org/abs/2011.12245): “This is consistent with our main result, and demonstrates that barren plateaus can lead to exponential scaling even for gradient-free optimizers.”
  - Deepen: not run yet

**Prior art found outside the knowledge base**

- arXiv:2505.05249, "Quantum Surrogate-Driven Image Classifier: A Gradient-Free Approach to Avoid Barren Plateaus": combines a gradient-free method with mid-circuit measurement and reset to avoid barren plateaus. It does not measure how a gradient-free optimizer's shot cost scales with qubit count under each mitigation, so the scaling question may remain open.

**Caveats**

- Barren-plateau-free models are often classically simulable (Cerezo et al., arXiv:2312.09121, not in this knowledge base); check whether each mitigated regime is.
- Mitigations were shown for specific settings (chemistry VQE, thermal-state PQCs); results may not transfer.

**Next steps**

1. Search the literature for gradient-free optimizers combined with each mitigation.
2. Simulate 4–12 qubit circuits with and without each mitigation; measure cost-function variance and the shots a gradient-free optimizer (e.g. Nelder–Mead, COBYLA) needs to reach a fixed accuracy, versus qubit count.
3. Fit exponential vs polynomial scaling; the hypothesis fails if the shot count still grows exponentially with the mitigation.

## QC-2

**Do two barren-plateau mitigations combine (chemical initialization × mid-circuit measurements)?** · priority medium · status open

Each mitigation is reported separately (2609.22729, 2406.14285); none of the 155 papers combines them. Deepen rated the composition conditional and proposed a 2×2 factorial.

- **Hypothesis:** chemical initialization and mid - circuit measurements may jointly constrain barren plateaus, so relieving one may shift the bottleneck to the other. (Frontier `3ddf8977a9da`, topic “barren plateaus”, rank 1)
  - Scores: support 0.8, relevance 0.864, novelty 0.696
  - [arxiv-2609-22729-p0002](https://arxiv.org/abs/2609.22729): “In the benchmarks considered here, chemically initialized starting points and variational trajectories show polynomial decay of local gradient variance with system size instead of the exponential BP-like decay observed for random controls, indicating that chemical initialization mitigates barren plateaus in the local optimization regions and highlights the trainability advantage of chemically motivated VQE strategies.”
  - [arxiv-2406-14285-p0059](https://arxiv.org/abs/2406.14285): “therefore, mid-circuit measurements, circuit pretraining, entanglement regularization to add terms to the cost function, and initial partitioning play on the entanglement entropy to better mitigate barren plateaus”
  - Deepen: verdict `all_links_supported`, links ['supported', 'supported'], composition `conditional`, knowledge-base novelty `no_overlap_found_in_snapshot`
  - Test plan (2x2 factorial): vary ['chemical initialization', 'mid - circuit measurements'], measure ['barren plateaus']. Fails if: A precisely measured absence of an interaction challenges compounding in barren plateaus; it does not refute individual effects of chemical initialization or mid - circuit measurements. Predefine a meaningful effect threshold.

**Caveats**

- The same classical-simulability caveat as QC-1.
- Interaction may be absent; a null result does not refute either effect alone.

**Next steps**

1. Run the 2×2 simulation: neither, each alone, both; measure gradient variance versus system size.
2. Predefine an effect threshold for "interaction".

## QC-3

**How much of the cosmic-ray penalty can correlation-aware decoding recover?** · priority medium · status open

Deepen marked this open problem contested: cosmic rays cause correlated errors at about 1/(10 min) (2402.03208), while accounting for correlated errors in decoding raises the threshold in concatenated codes (2407.16176). The conflict is partly a meaning slip ("taking into account" correlations), but it points at a quantitative question.

- **Hypothesis:** Cosmic rays may reduce the error threshold through correlated errors. (open problem phrased for Deepen)
  - [arxiv-2402-03208-p0002](https://arxiv.org/abs/2402.03208): “Cosmic rays caused correlated errors at a rate of 1/(10 min), accounting for 17pm1% of all such events.”
  - [arxiv-2407-16176-p0047](https://arxiv.org/abs/2407.16176): “However, for higher levels of concatenation, taking into account the correlated errors significantly reduces the logical error rate and increases the error threshold.”
  - Deepen: verdict `contested`, links ['supported', 'supported'], composition `incompatible_direction`, knowledge-base novelty `no_overlap_found_in_snapshot`
  - Test plan (mediation): vary ['Cosmic rays'], measure ['the error threshold']. Fails if: the error threshold does not change when Cosmic rays varies with the controls fixed, or holding correlated errors fixed leaves the effect unchanged.

**Caveats**

- This is a known research direction, not a new discovery.
- Radiation events are bursts that can exceed what decoders can model.

**Next steps**

1. Review the literature on radiation-aware and correlation-aware decoders.
2. Simulate a surface code with injected radiation-like bursts; compare a standard decoder with one given the burst model.

## QC-4

**Is error mitigation useful only where classical simulation is already easy?** · priority medium · status open

Recoverable observables must be dominated by low-weight Pauli operators, which are easy to simulate classically (2607.25746), and mitigation needs superpolynomially many samples even at low depth (2210.11505). Together they suggest a squeeze: the regime where mitigation is cheap may overlap the regime where it is unnecessary.

- **Hypothesis:** low weight Pauli operators and samples may jointly constrain error mitigation, so relieving one may shift the bottleneck to the other. (Frontier `801cef0c64c7`, topic “error mitigation”, rank 8)
  - Scores: support 0.8, relevance 0.757, novelty 0.696
  - [arxiv-2607-25746-p0061](https://arxiv.org/abs/2607.25746): “Intuitively, this is because observables whose ideal expectation values are recoverable via error mitigation must be dominated by low-weight Pauli operators, which are simultaneously easy to simulate classically.”
  - [arxiv-2210-11505-p0016](https://arxiv.org/abs/2210.11505): “By picking, e.g., the parameter s = Ω(n/ log2(n)), we see that even at the low depth D = poly log log(n), error mitigation already requires superpolynomially-many samples.”
  - Deepen: verdict `all_links_supported`, links ['supported', 'supported'], composition `conditional`, knowledge-base novelty `no_overlap_found_in_snapshot`
  - Test plan (2x2 factorial): vary ['low weight Pauli operators', 'samples'], measure ['error mitigation']. Fails if: A precisely measured absence of an interaction challenges compounding in error mitigation; it does not refute individual effects of low weight Pauli operators or samples. Predefine a meaningful effect threshold.

**Caveats**

- Both papers are about worst-case or asymptotic bounds; practical instances may fall outside them.
- Likely discussed in the field already.

**Next steps**

1. Check whether a paper states the trade-off directly.
2. For a benchmark family, map observable weight versus mitigation sample cost versus classical simulation cost.

## QC-5

**Distillation speed versus circuit error in magic-state factories** · priority low · status open

Too rapid distillation discards magic states (2407.07394); a faulty magic state causes a circuit error with probability equal to its infidelity (1905.06903).

- **Hypothesis:** rapid distillation speed may increase error of circuit outcome through discarded magic states (read as faulty magic state). (Frontier `1807b3734c6f`, topic “magic state distillation”, rank 6)
  - Scores: support 0.8, relevance 0.852, novelty 0.619
  - [arxiv-2407-07394-p0024](https://arxiv.org/abs/2407.07394): “Finally, a too rapid distillation speed leads to discarded magic states.”
  - [arxiv-1905-06903-p0011](https://arxiv.org/abs/1905.06903): “The infidelity corresponds to the probability that a faulty magic state that is used to perform a gate in a quantum circuit will lead to an error of this circuit’s outcome [30].”
  - Deepen: verdict `all_links_supported`, links ['supported', 'supported'], composition `requires_review`, knowledge-base novelty `no_overlap_found_in_snapshot`
  - Test plan (mediation): vary ['rapid distillation speed'], measure ['error of circuit outcome']. Fails if: error of circuit outcome does not change when rapid distillation speed varies with the controls fixed, or holding discarded magic states fixed leaves the effect unchanged.

**Caveats**

- A speed/fidelity trade-off is known in outline; the chain mixes "discarded" with "faulty" states (composition requires review).

**Next steps**

1. Read 2407.07394 for how discarded states are handled; the link to output error may not hold if discarded states are never used.

## QC-6

**Do radiation bursts correlate failures inside magic-state factories?** · priority low · status known in literature

Cosmic rays cause correlated errors (2402.03208); faulty magic states cause circuit errors (1905.06903). If a burst hits a factory, many distilled states could fail together.

- **Hypothesis:** Cosmic rays and faulty magic state may jointly drive correlated errors, and their effects may compound. (Frontier `74c9ad9a97e2`, topic “magic state distillation”, rank 25)
  - Scores: support 0.8, relevance 0.621, novelty 0.668
  - [arxiv-2402-03208-p0002](https://arxiv.org/abs/2402.03208): “Cosmic rays caused correlated errors at a rate of 1/(10 min), accounting for 17pm1% of all such events.”
  - [arxiv-1905-06903-p0011](https://arxiv.org/abs/1905.06903): “The infidelity corresponds to the probability that a faulty magic state that is used to perform a gate in a quantum circuit will lead to an error of this circuit’s outcome [30].”
  - Deepen: not run yet

**Prior art found outside the knowledge base**

- arXiv:2405.00146, "Averting multi-qubit burst errors in surface code magic state factories": studies cosmic-ray and TLS burst errors in magic-state factories directly.

**Caveats**

- Speculative; not checked with Deepen. The two sources study different systems.

**Next steps**

1. Run Deepen with the novelty review on this entry.
2. Search for radiation effects on distillation factories.

## Coverage gaps

These open problems, phrased as hypotheses, found no usable evidence chain. The cause is thin coverage (most papers on them were abstracts only), not evidence against them. Adding full-text papers is the next step.

- Noise may reduce quantum advantage through classical simulation.: `unsupported`, links ['weak', 'weak']
- Barren plateaus may constrain variational quantum algorithms through classical simulability.: `unsupported`, links ['weak', 'missing']
- Circuit size may increase error mitigation cost through sampling overhead.: `unsupported`, links ['weak', 'missing']
- Quantum LDPC codes may reduce qubit overhead through encoding rate.: `unsupported`, links ['weak', 'weak']
- Quantum LDPC codes may increase decoder complexity through long-range connectivity.: `unsupported`, links ['missing', 'missing']
- Two-level system defects may reduce qubit coherence through dielectric loss.: `unsupported`, links ['missing', 'weak']

## Reproduce

Ingest `tests/fixtures/quantum_computing` into a namespace, then pass a hypothesis back to Deepen:

```python
app.ask("Deepen this.", deepen={"hypothesis": "<hypothesis text>", "novelty": True})
```

Regenerate this page with `docs/reviews/2026-11-25-quantum-computing/scripts/build_leads.py`.
