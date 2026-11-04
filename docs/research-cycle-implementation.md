# Research/cycle implementation record

Design specs were committed and pushed as b16eb19 before runtime work began.
Implementation branch: codex/research-cycle-nodes. No published package changes.

## Implemented initial stage

- Curated research plans, keyword spans, questions, expanded instructions, stable
  plan hashes and candidate coverage for ordinary document requests.
- One authorized snapshot; separate named topic recall plus one explicit relation
  layer; atomic quotations and existing inverse-verified style path retained.
- Ordinary draft genres with explicit recipient metadata and missing-context
  clarification; strict retains its existing behavior.
- Iterative multiple-cycle core, path-local repeat pruning, alternative paths,
  six-channel symbolic receipts, configurable bounded rounds and resource ledger.
- Snapshot adapter with source IDs, quotation offsets/hashes, tenant/as-of scope.
- Explicit Python/HTTP cycle_search routing, strict disable and OpenAPI/flag map.

See [usage and implementation limits](research-cycle-user-guide.md) for the
distinction between lexical candidates and semantic identity validation.

## Remaining design stages

The full proposal includes features beyond this initial implementation:
canonical sense IDs and cross-store migration; checkpoint/resume; calibrated
vector-based prioritization; adaptive multi-pass research with a request-wide
persisted budget; broader clarification/constraint/genre grammars. Email-native presentation
and longer bounded composition are implemented in the follow-up below. Those are not claimed complete. Current bounded snapshot execution
avoids cross-store migration and hidden child retries rather than pretending
these contracts already exist.

## Verification

Targeted regression command:

```shell
python -m pytest -q -o addopts='' tests/test_research_cycles.py tests/test_document_workflow.py tests/test_document_tone.py tests/test_flag_contract.py tests/test_http_schema_contract.py tests/test_strict_evidence.py tests/test_strict_evidence_v2.py
```

Result: 125 passed. Tests include >10-edge closure,
multiple loops, alternate paths, limits, cancellation, shared core budgets,
source filtering, proof offsets, document research, draft recipients and strict
isolation. No customer/clinical benchmark or 100,000-hop completion is claimed.

Final full default suite, using the isolated native PostgreSQL/pgvector test
database: **953 passed, 56 skipped, 3 existing xfailed**, six existing NumPy
warnings, 104.95 seconds. The 54 opt-in integration cases were not enabled;
two optional extractor checkpoints were absent. This is not a full-live suite.

```shell
python -m pytest -q -o addopts='' -o faulthandler_timeout=30 --junitxml=build/research-cycle-tests.xml
```

The command used VECTORPRISM_PG_DSN for a separate disposable database with a
bounded connection timeout. Raw receipts remain under build/research-cycle-tests.*.
A pure source-snapshot example found two Alpha cycles of lengths 2 and 3;
the corresponding article plan produced five research questions and four
attributed records. Example output is in build/research-cycle-examples.json.

After the full run, a snapshot-count metadata correction was verified with the
125-test targeted set (4.26 seconds); research selection and strict behavior
remain covered. No broad rerun was required for that reporting-only correction.

## Long-document correction follow-up

See [the long-document composition contract](long-document-composition-spec.md).
The 20-record document bottleneck is replaced with word-based atomic pagination,
up to 500 explicit source items, ordinary neutral inverse-verified composition,
research-aware required coverage, and native email/letter draft layouts. Strict
mode retains quotation-only composition. Explicit StyleOptions budgets still
reject rather than drop claims. Per-subject pronoun checks were strengthened.

The focused document/research/flag/response regression set passes 136 tests.
Actual Appliance runs on the isolated database produced a 1,013-body-word article
from 66 selected records, 60 individually presented source items, and a concise
21-body-word email containing all four authorized facts without pagination.
The retention dataset deliberately repeats a structure with distinct generation
numbers to test selection; this does not establish editorial quality.

Full-suite receipt: build/long-document-tests.xml and .log. Actual live responses:
build/long-document-live-examples.json. Complete example transcripts are linked
from the user guide. No new package or PyPI upload is part of this correction.

Final follow-up default suite: **967 passed, 56 skipped, 3 existing xfailed**,
six existing NumPy warnings, 107.66 seconds. The 54 opt-in integration cases
remain disabled and two optional extractor checkpoints remain unavailable.
This is not a full-live or independent benchmark. Final focused set: 136 passed.
