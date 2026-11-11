# CPU-LLM enterprise pilot runbook

## Customer acceptance

Start with covenant verification over approved structured inputs. For each reviewed case, record the source ID, threshold and operator, numerator and denominator, rounding policy, expected ratio and decision, and required citation or calculation receipt. Freeze the cases before running. Keep customer documents and labels in the customer's approved environment.

- Include values below, exactly at, and above the threshold. Include a rounding tie, missing inputs, a zero denominator, and conflicting source values. Review the expected calculations independently.
- Include caller and tenant boundary cases and a rejected unauthenticated request. Require zero unauthorized disclosures and exact agreement on deterministic decisions and supported citation provenance.
- Use 95% supported correctness as the existing engineering target for general requests. Agree separately with the customer on scoped pilot thresholds, acceptable abstentions, workload size, response latency, and recovery objectives. Record the reviewer and the sign-off.
- Use the frozen [request-pipeline benchmark](benchmark-capability-1.12.1-spec.md) for general routing and evidence behavior. The live `tests/test_domain_gap_fixes_live.py` cases exercise structured finance requests, including missing and zero inputs. Their results are engineering evidence for the pilot.

## Deployment and operations

Use the exact verified wheel and compatible PostgreSQL with pgvector. Prepare the encoder cache before deployment. Run the authenticated service with a dedicated working directory and database account, restrictive permissions on credentials and state, and a managed TLS gateway where clients connect over a network.

```shell
python -m pip check
cpu-llm-serve --secrets credentials.json --ingest-root approved-input --audit-db mutation-audit.sqlite
```

The built-in HTTP server handles one request at a time. Use the lab measurement to set ingestion windows and pilot latency expectations. The operations benchmark exercises overlapping clients, an interrupted replacement, and restore on an isolated loopback database named `enterprise_ops`. Enable pgvector and prepare the model cache before the run.

```shell
python tools/benchmarks/enterprise_operations.py --pdf /path/to/test.pdf --out build/enterprise-ops --pg-bin /path/to/postgres/bin
```

## Backup, restore, upgrade, and rollback

1. Quiesce writes and stop the service. Capture the wheel version and hash, a PostgreSQL custom-format dump, the deployment's `.chorusgraph` directory, credentials through the approved secret-management process, and the configured audit database. Store the backup with restricted permissions.
2. Restore to an isolated PostgreSQL database and a separate working directory. Restore the matching local stores and assets. Verify the active chunk count, a known strict answer with its citation, caller scoping, and audit receipt integrity before switching traffic.
3. Stage an upgrade in a new virtual environment. Run `pip check` and smoke queries against the restored copy. Stop writes, take a final coordinated backup, switch the service environment, and check the same known queries again.
4. If the upgrade fails, stop writes and return to the tested prior environment. Restore the coordinated backup if the release changed persisted formats or if state checks fail. Before restoring an older snapshot, record any post-upgrade mutations that need reconciliation.

## Team access and audit

Set `"revoked": true` or remove the affected credential in an atomic credential-file replacement. The next authentication reads the updated file. Requests already authenticated can finish. Use separate high-entropy credentials per team caller and scoped admin access for deletion.

`--audit-db` records metadata for authorized ingest, correction, confirmed chunk deletion attempts, and source deletion. It stores caller, tenant, request ID, action, target IDs, timestamps, and returned outcome. A `started` record with no completion requires reconciliation with the stores. Mutation and audit storage use separate transactions. Keep the SQLite audit file with the coordinated backup and restrict access to it. `--audit-retention-days` prunes completed events on the next audited mutation. Backups and incomplete records require their own retention handling.

## Incident response

Assign a named operator and escalation contact before pilot access. For an access or evidence incident, stop affected writes, revoke the implicated credential when appropriate, preserve the audit database and request IDs, and verify the affected scope. For ingestion or availability incidents, check the health of PostgreSQL and the encoder, compare inventory with the last verified snapshot, and run the restore procedure if required. Document the impact, recovery checks, and approval to resume traffic.

## Lab results

- The installed 1.13.1 wheel scored 390/460 on the fresh request benchmark, including 211/278 full contract passes on gold-expected answer rows. Strict evidence passed 42/42 fictional cases against 25/42 for the local baseline. Six fictional covenant acceptance cases passed exact arithmetic and refusal checks.
- The 162-page PDF imported 265 chunks in 38.77–40.67 seconds across two runs. A strict query before ingestion took 27.1–28.5 ms. Three overlapping strict requests per run all succeeded and waited about 38.8–40.7 seconds on the serial service.
- Terminating the ingest subprocess at its second encoder batch preserved the original active chunk. A fresh retry succeeded. Restoring the PostgreSQL dump and local stores preserved the 265-chunk inventory and known strict answer. The restored audit file matched the original and contained both ingest receipts.
- Separate wheel environments completed a 1.13.0 to 1.13.1 upgrade and rollback to 1.13.0 against the same isolated database and working directory. Both the original and post-upgrade lookup passed after rollback.

Customer data, identity-provider configuration, signed acceptance, named support ownership, and sustained production load remain pilot inputs.

The saved 1.13.1 request scores show 229/278 answer-like responses (82.4% coverage) and 211/229 full contract passes among delivered answers (92.1%). On gold-expected answer rows, 30 insufficient-evidence replies and 17 clarification replies had no flagged false assertion, and two replies were budget refusals. Across the suite, 84 gold-expected abstentions passed and the scorer flagged zero false assertions. These figures describe the synthetic suite and its configured checks. Whether a missed row was truly answerable requires review of the prompt and source evidence.
