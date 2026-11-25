# Frontier/Deepen v2: before/after regression

Date: 2026-11-26. **Before** is `71713c7`, the v2 spec commit before any code change. **After** is `1bd981c`. Both
used the same four namespaces, prompts and parser (`en_core_web_lg`), with no re-ingest. Scripts:
`scripts/eval_v2.py` and `scripts/time_ingest.py`. Raw data: `before.json`, `after.json` and `ingest-timing.json`.

## Test suite

1,417 passed, 56 skipped, 3 xfailed. The same 3 failures predate v2 (`test_cycle_composition` ×2,
`test_request_pipeline_benchmark`). 1.16.0 had 1,343 passed.

## Frontier, default options

| Namespace | Entries returned | Artefact entries (before → after) | Leading-check verdicts after |
|---|---|---|---|
| AI bottlenecks (5 topics) | 207 → 207 | 0 → 0 | 25 all links supported |
| DL generalization (5) | 207 → 207 | 2 → 0 | unchanged, including the contested grokking entry |
| Consciousness (5) | 140 → 140 | 0 → 0 | unchanged |
| Quantum computing (12) | 512 → 501 | **67 → 6** | 6 contested → **4 contested + 2 `bridge_mismatch`** |

- On quantum computing, removing artefact entries shortened three lists: barren plateaus 28 → 22, two-level
  systems 15 → 10, leakage unchanged at 19. The other topics still return 50.
- The six remaining artefact matches are terms such as "Realizing the full potential of quantum", which are
  truncated rather than artefacts in the spec's sense. This is a known gap.
- Frontier time on quantum fell from 202 s to 170 s.
- Lead statuses from the leading checks:

  | Namespace | `testable` | `needs_review` | `needs_semantic_resolution` | `contested_tension` |
  |---|---|---|---|---|
  | Quantum | 8 | 19 | 29 | 4 |
  | AI bottlenecks | 5 | 17 | 3 | — |
  | Consciousness | 9 | 7 | 3 | — |

## Frontier with `screen`

- No entry built on document artefacts remains.
- Generic entries are dropped, so lists shrink where the topic has few specific entries. On quantum computing,
  10 of 12 topics still return 50. Barren plateaus returned 11, two-level systems 3, and consciousness's "hard
  problem" 1.
- The dropped entries are listed in `screen.dropped_ids`. A follow-up could demote generic entries instead of
  dropping them, so a full list is kept.
- `needs_semantic_resolution` dominates the shortlist checks (91 of 160 on quantum computing). Most Frontier entries
  join papers through a "(read as …)" bridge, which is exactly what the composition gate flags.

## Deepen on fixed hypotheses

| Hypothesis | Before | After |
|---|---|---|
| Cosmic rays reduce the threshold through correlated errors | contested, mediation plan | contested, `contested_tension`, `resolve_first` |
| Reset reduces Z error through leakage-induced correlated errors | contested | **`bridge_mismatch`**, `needs_semantic_resolution` (the counter-source was about X/Y errors) |
| Chemical initialization and mid-circuit measurements jointly constrain barren plateaus (text form) | contested, 2×2 factorial | contested, `resolve_first` |
| Low-weight Pauli operators and samples jointly constrain error mitigation | 2×2 factorial varying Pauli weight | **stratified** design, `testable` |
| Rapid distillation speed increases circuit error through discarded magic states | mediation plan | `needs_semantic_resolution` (discarded ≠ faulty) |
| Leakage → logical errors; two-level-system defects → coherence | partly supported or unsupported | same verdicts, labelled **`coverage_gap`** |
| Error-mitigation cost grows exponentially with circuit size; qLDPC codes reduce overhead; noise removes quantum advantage | `needs_clarification` | **read** (direct or chain), unsupported, `insufficient_evidence` |

Candidate controls no longer include "D. Implications for Future Processors" or "issues".

## Ingestion

On the 3,369-chunk quantum namespace, a per-document ingest went from 2.94 s to 2.51 s by default.
`consolidate="end"` takes 0.88 s per document for folders.

## Remaining weaknesses

- **Truncated terms survive:** "universal quantum", "Realizing the full potential of quantum", "Devised sticking".
- **Hub chains can still be `testable`.** "Ultra-short pulses may increase shots through qubit" has no meaning
  bridge and a conditional composition, but goes through the generic hub "qubit". The screen removes it; the
  default list does not.
- **`screen` drops rather than demotes,** so short lists can come back as a `shortage`.
- **Quarantined plans don't keep `variable_types`.**
