# Invention constraint evaluator

A research brief can name a mechanism and its observables. A numerical scan additionally requires a named executable model, explicit parameter axes with units, and independent, sourced observable limits. Callers provide a trusted Python model adapter. The evaluator never executes source text or formulas extracted from the knowledge base.

The adapter receives a parameter point and returns predictions keyed by observable. Each observable has a declared unit. Constraints use inclusive lower and upper bounds, with at least one bound present, and carry a source reference. Supply separate constraints or scans for distinct experimental assumptions. For example, a measured decay half-life limit and an inferred mass limit are separate constraints.

The evaluator scans a bounded Cartesian grid in deterministic order. It records each point's predictions and failed constraint identifiers. Adjacent accepted and rejected grid points bracket a sampled transition. The grid spacing determines the resolution, and an empty set of accepted samples does not exclude unsampled points. Evaluation errors stop the scan.

The Python invention workflow exposes the scan through the appliance after a cited hypothesis has been selected. A scan is an explicit action with supplied inputs. The hypothesis receipt does not imply that a scan ran. The first regression uses a synthetic model with a known intersection. A leptogenesis scan requires an independent implementation of the cosmological and laboratory predictions and validated numerical inputs.

## Illustrative leptogenesis adapter

`Appliance.scan_leptogenesis(hypothesis, axes=..., limits=...)` runs a normal-ordering, hierarchical, unflavored N1 approximation on the Casas–Ibarra slice `(0, cos(z), sin(z))`. Supply axes for `m_lightest` in eV, `M1` in GeV, and `re_z` and `im_z` in radians. Optional `alpha21` and `alpha31` axes are in radians and default to zero. The receipt records these assumptions. The adapter computes the imaginary parts of the squared complex entries directly and converts the light-mass factor from eV to GeV before evaluating the CP asymmetry.

Supply sourced constraints for `eta_B` and `m_beta_beta`. An optional `sum_m_nu` bound can be evaluated in the same scan. Use separate runs for different nuclear matrix element scenarios. The adapter predicts an effective mass in eV. A direct half-life bound requires an additional decay model. See the [complete KamLAND-Zen analysis](https://journals.aps.org/prl/abstract/10.1103/jkf6-48j8).

This adapter verifies the numerical workflow and the diagnostic scan. A physics benchmark requires reproducing a published model point with its inputs and conventions, including [flavor effects](https://arxiv.org/abs/hep-ph/0601084) where applicable. Boundary claims also require checking finer grids. Chat follow-ups can describe a scan, and numerical execution requires the explicit Python call with caller-supplied axes and limits.
