# CPU-LLM whitepaper addendum

## Prompt triggers and execution routes

This addendum describes routing in CPU-LLM 1.13.1. It supplements the versioned implementation whitepaper.

The classifier recognizes request forms and selects optional graph nodes.
Ordinary requests enter the guarded retrieval graph, where the six channel
nodes evaluate their signals. An explicit request can select a separate
document, invention, CrossDomain, or management route before graph entry.
Strict evidence policy governs supported quotations and calculations.

- `What did John eat?` requests the event frame for John and the action `eat`. The engine verifies the object against the stored passage.
- `Search deeply for apple.` requests wider retrieval. Python callers can set `deep=True`. Asking for more sentences changes the response budget.
- `Calculate 17 times 24.` requests arithmetic. Python or HTTP callers can set `discover=True` to request discovery after the ordinary reply.
- `Write a detailed report about Helios.` requests a cited document. `Show relationship loops for Alpha.` requests bounded cycle exploration.
- `Invention: Leptogenesis.` requests a labeled hypothesis. A matching built-in profile can run a numerical scan with stated assumptions.
- `Research Casas-Ibarra using KBs: physics, math.` requests CrossDomain. Structured numeric claims can delegate to Constraint Check. `Constraint Check: Leptogenesis using KBs: physics, math, experiment.` invokes the comparison directly.
- `List chunks for notes.pdf.` requests scoped inventory. `Delete chunk notes-p0001.` requests an exact preview. The deletion API enforces confirmation and team admin permissions.

Inspect `routing.executed_nodes` and `routing.post_stages` where available.
The [trigger guide](../prompt-flag-map.md) explains route conditions and
precedence. The [JSON registry](../prompt-flag-map.json) lists flags and
consumers for integration tests.
