# QC-7 pilot: do mid-circuit measurements offset the qudit amplification of barren plateaus?

**Lead.** Frontier entry `af462610d15d`, rated `testable` by Deepen v2. The receipts are in
[qudit-lead.json](../../reviews/2026-11-26-frontier-deepen-v2/qudit-lead.json):

> Gains in barren plateaus from dimension of qudits may be offset by mid-circuit measurements.

It rests on two citations. The first is arXiv 2405.08190, *Barren plateaus are amplified by the dimension of
qudits* (cited by title only, because it is abstract-only in the knowledge base). Its abstract calls for "further
scrutiny" of mitigation techniques for qudits. The second is arXiv 2406.14285, which lists mid-circuit measurements
among barren-plateau mitigations.

**Model.** A toy operationalization, fixed before running; see `simulate.py`.
- Density-matrix simulation of n qudits of dimension d, with 2n layers.
- Each layer applies random parameterized single-qudit rotations, then generalized controlled-phase gates in a brick
  pattern.
- The cost is local: the probability that qudit 0 is |0⟩.
- The gradient is taken with respect to a first-layer angle, by central difference.
- 400 random samples per point.
- **Mitigation:** after every second layer, measure the qudit farthest from qudit 0 and reset it to |0⟩.

**Pre-registered reading** (`analyze.py`):
- **supported in this model** if the mitigation raises the gradient variance at every d and its benefit grows
  with d;
- **refuted in this model** otherwise.

## Result

| d | Decay of log Var per added qudit (unmitigated) | With mitigation | Variance ratio, mitigated/unmitigated (n = 3, 4) |
|---|---|---|---|
| 2 | −0.57 | −0.53 | 0.88 |
| 3 | −0.90 | −0.86 | 0.84 |
| 4 | −1.59 | −1.96 | 0.67 |

- **Qudit dimension amplifies barren plateaus.** The decay steepens from −0.57 to −0.90 to −1.59 as d goes from 2
  to 4. This reproduces the claim of arXiv 2405.08190 in this model.
- **This mitigation does not offset it.** It lowers the gradient variance at every d, and the loss is largest at
  d = 4.

**Verdict: refuted in this model, for this operationalization.**

## What this does and does not show

- **It tests one simple version of "mid-circuit measurements"**: a single measure-and-reset far from the cost qudit,
  without feedback. The surveyed mitigations include other schemes: measurements with feed-forward,
  entanglement-entropy control and pretraining. Those are not tested here.
- **The model is small:** n ≤ 6, d ≤ 4, one circuit family, one local cost and 400 samples per point. The relative
  standard error of each variance is roughly ±10–20%. The d = 4 effect (×0.67) and the steeper decay are larger than
  that, but the n = 2 points are dominated by the reset sitting next to the measured qudit.
- **The chemical-initialization and MPQC variants were not tested.** Their methods cannot be reproduced from
  abstracts.

## Next steps, if pursued

1. A measurement variant with feed-forward, or one that targets entanglement entropy near the cost qudit.
2. Identity-block or small-angle initialization, as a standard baseline mitigation, across d.
3. Larger n via tensor-network or trajectory simulation.

Reproduce: `python simulate.py results.json 400 && python analyze.py results.json`.
