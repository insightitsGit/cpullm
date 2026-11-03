# Database-backed tone demonstration

Run date: November 3, 2026. Six fictional paragraphs were ingested through `Appliance.catalog_chunks`; each prompt ran twice through `Appliance.ask`, with and without style. This is a full database/encoder/retrieval/pipeline run, not prepared node inputs.

Runtime revision: `5766172`. The runner had the connection-preflight/progress changes saved in this checkout; `freeze.json` records its exact SHA-256. Eight cases completed. Canonical replies and canonical proof fields matched in every pair. Five published companions passed the inverse-grammar verifier; the remaining cases intentionally skipped or disabled style. These are engineering examples, not independent accuracy measurements.

## Cause and repair

The default development database endpoint on port 5433 was unavailable, and Docker was stopped. The existing isolated PostgreSQL 18/pgvector cluster under `build/join-audit-pgdata` was started on loopback port 55433. A dedicated `tone_demo_20261103` database and fresh appliance namespace were used; the unrelated PostgreSQL service on port 5432 was not modified.

`tools/tone_chat_demo.py` now accepts `--dsn`, honors `VECTORPRISM_PG_DSN`, checks connectivity and the installed vector extension before loading the appliance, sets a five-second connection timeout, and prints startup/ingestion progress. An unreachable endpoint was also checked: it exited with a clear error and did not create run artifacts.

## Actual outputs

### formal-color

Prompt: What color is the Aster?

Status: `generated`; alignment: `supported`.

> The color of the Aster is blue.

### friendly-location

Prompt: Where does the Aster live?

Status: `generated`; alignment: `supported`.

> You can find the Aster in coastal waters.

### analytical-weight

Prompt: What is the weight of the Aster?

Status: `unchanged`; alignment: `supported`.

> The weight of the Aster is 12.5 pounds.

### five-fact-composition

Prompt: Tell me the color, habitat, shape, material, and weight of the Aster.

Status: `generated`; alignment: `supported`.

> The Aster is blue, and you can find the Aster in coastal waters. The Aster has a round shape, and the Aster is made of steel. The Aster weighs 12.5 pounds.

### poetic-fallback

Prompt: What color is the Aster?

Status: `generated`; alignment: `neutral_fallback`.

> The color of the Aster is blue.

### relationship-restriction

Prompt: What color is the Aster?

Status: `skipped`; alignment: `not applicable`.

Reason: relationship_tone_conflict

### strict-label

Prompt: What is the strength of Fictional DemoMed?

Status: `disabled`; alignment: `not applicable`.

Reason: Strict evidence bypasses the tone node.

### finance-boundary

Prompt: Decide this LedgerCovenant test. / threshold: 4.50 / numerator: compliance_certificate 9000001 / denominator: compliance_certificate 2000000 / 

Status: `skipped`; alignment: `not applicable`.

Reason: no_supported_immutable_frame

## Replay

Start a PostgreSQL database with the `vector` extension and configure `VECTORPRISM_PG_DSN` to its connection URI. With cached encoder assets, set `HF_HUB_OFFLINE=1` and `TRANSFORMERS_OFFLINE=1`, then run:

```shell
python tools/tone_chat_demo.py --out build/tone-chat-new-run
```

Use a new output directory. The run adds its own isolated namespace and six fictional facts. The database must already exist; the runner does not provision a server or alter unrelated databases. Raw inputs, full replies, proofs and the run receipt are retained alongside this transcript.
