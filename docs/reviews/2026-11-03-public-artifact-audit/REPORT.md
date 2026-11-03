# Public-artifact audit response and remediation

Date: November 3, 2026. The supplied audit was treated as findings to verify,
not as proof of release or clinical readiness.

## Confirmed and corrected

The 1.11.0 PyPI wheel was downloaded independently. Its SHA-256 matches the
release receipt, and all 113 Python files match commit `75425fc` after line-ending
normalization. Commits `75425fc`, `0102bc0` and `92002fd` are ancestors of public
main and their GitHub pages returned HTTP 200. An annotated **v1.11.0** tag was
created and pushed at `75425fc`, not at later documentation or patch commits.

The public product URL returned HTTP 200 with the expected Evidence-Based AI
Engine title and 1.11.0 text. This verifies page presence/version, not every
marketing statement, legal liability or clinical compliance.

The README already had a complete pgvector Docker command. Added:

- Root `docker-compose.yml`, loopback-only port binding, final TCP readiness
  check and public-schema vector-extension initialization on a new volume.
- `docs/development-database.md`, with matching DSNs, 5433/5434 alternatives,
  explicit credentials/database names and existing-volume behavior.
- `docs/offline-setup.md`, with connected preparation, cache transfer and offline
  verification using HF_HOME/HF_HUB_CACHE before imports. The helper can verify
  cached encoder loading with all TCP connection attempts forbidden.
- `docs/openapi.json`, validated as OpenAPI 3.1, with all four authenticated POST
  routes, ordinary/strict examples, supported fields and strict-floor precedence.
  It does not invent a served Swagger/OpenAPI endpoint or universal body validation.
- Manual and package-description links/snippets, regression checks that keep the
  schema's field whitelist aligned with the implementation, and future-sdist
  inclusion of Compose/init SQL. Published 1.11.0 files were not rewritten.

Encoder cache verification passed using snapshot
`e8c3b32edf5434bc2275fc9bab85f82640a19130`, producing a 768-dimensional embedding
while connections were forbidden. An empty cache failed clearly with exit 2.
This is retrieval-encoder verification, not an assertion that optional FLAN-T5,
spaCy or coreference models are installed or that all runtime egress is firewalled.

## Additional real defect discovered

The deeper HTTP test exposed a runtime problem missing from the audit. Published
1.11.0's threaded server reuses a cached tenant appliance across request threads.
Its SQLite-backed format/graph connection belongs to the creation thread.
Ordinary requests can therefore raise sqlite3.ProgrammingError and disconnect,
even while a strict source lookup succeeds.

The initial preconstructed-appliance test was followed by a normal **lazy
factory** reproducer, matching the shipped service's ownership pattern. The
published wheel passed the strict call and failed all three ordinary clients in
that run. This was not merely a claim based on a synthetic or invalid fixture.

The **1.11.1 patch** serializes requests on the serving thread where its lazy
factory constructs appliances. Responses close connections so an idle keepalive
cannot occupy the serial server. Separate-client SQLite and keepalive regressions
were added. Embedders must construct their thread-affine appliance on the serving
thread; supplying an object constructed on another thread is still invalid.

The patched source and then the actual installed patch wheel passed the same
strict lookup and all three ordinary clients. The full source suite passed
**905**, skipped **56**, and retained **3** existing expected failures and six
existing NumPy warnings. Service/schema/thread/keepalive checks passed **19**.
The packaged healthcare demo passed **12/12** before and after the patch in the
new PyPI-install environment, with cached assets and an isolated native database.
These are engineering checks, not an aggregate accuracy or clinical-safety rate.

## Still open: Docker host and patch publication

`docker compose config --quiet` passes. Docker Desktop was started for the actual
container check, but its backend crashes initializing the `dockerInference`
socket before the Engine becomes available. No factory reset, data deletion or
system-wide repair was performed. **The actual Compose/pg16 container smoke is
not claimed passed.** It must be rerun on a working Docker installation.

The audit's pg16/5434 environment is historical; the latest release and this
native smoke used PostgreSQL 18/pgvector on port 55433. Those observations do not
substitute for the blocked Docker run. The test used a new virtual environment
on the same Windows host, not a different physical machine or a cold model download.

1.11.1 wheel/sdist artifacts are prepared and validated; publishing remains the
maintainer's action. Until that upgrade, do not announce shared ordinary HTTP
service as corrected in the already published 1.11.0. Its original source tag
and distribution hashes remain valid historical provenance.

## References and receipts

- [Patch notes](../../releases/1.11.1.md) and [build validation](../../releases/1.11.1-build-validation.md).
- `public-links.json`, `product-page-check.json`, `release-source-parity.json`.
- `offline-encoder.json`, `released-http.json`, `installed-patch-http.json`.
- HTTP and full-regression JUnit receipts alongside this report.
- [Hugging Face cache layout](https://huggingface.co/docs/huggingface_hub/en/guides/manage-cache)
  and [environment variables](https://huggingface.co/docs/huggingface_hub/en/package_reference/environment_variables).
- [pgvector Docker instructions](https://github.com/pgvector/pgvector#docker).
