# Invention constraint evaluator

A research brief can name a mechanism and its observables. A numerical scan additionally requires a named executable model, explicit parameter axes with units, and independent, sourced observable limits. Callers provide a trusted Python model adapter. The evaluator never executes source text or formulas extracted from the knowledge base.

The adapter receives a parameter point and returns predictions keyed by observable. Each observable has a declared unit. Constraints use inclusive lower and upper bounds, with at least one bound present, and carry a source reference. Supply separate constraints or scans for distinct experimental assumptions. For example, a measured decay half-life limit and an inferred mass limit are separate constraints.

The evaluator scans a bounded Cartesian grid in deterministic order. It records each point's predictions and failed constraint identifiers. Adjacent accepted and rejected grid points bracket a sampled transition. The grid spacing determines the resolution, and an empty set of accepted samples does not exclude unsampled points. Evaluation errors stop the scan.

The Python invention workflow exposes the scan through the appliance after a cited hypothesis has been selected. A scan is an explicit action with supplied inputs. The hypothesis receipt does not imply that a scan ran. The first regression uses a synthetic model with a known intersection. A leptogenesis scan requires an independent implementation of the cosmological and laboratory predictions and validated numerical inputs.
