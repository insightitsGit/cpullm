# Clean installation audit — 2026-10-28

An isolated Windows x64 / Python 3.12.10 installation reproduces a first-ingestion
failure in Git revision `a9c4591`. Building the package itself succeeds. No error
log or platform information was available from the reporting user, so this is a
confirmed independent reproduction, not identification of their exact failure.

## Reproduction and cause

The audit exported committed Git source, created a virtual environment with
`include-system-site-packages = false`, upgraded pip, and followed the README's
`python -m pip install -e .`. Dependency resolution and installation succeeded.
`pip check` reported no broken requirements. The main package, pipeline,
retrieval, ingestion and server modules all imported.

An isolated `python -m build` also produced both an sdist and a wheel. The wheel
contains the VectorPrism checkpoint and nine data assets. Installing that wheel
and importing from its `site-packages` directory succeeded. Server `--help`
succeeded. These checks alone did not expose the ingestion problem.

With a separate PostgreSQL 18 database and pgvector, calling `index_chunks` on
three short facts failed:

```text
ModuleNotFoundError: No module named 'community'
RuntimeError: networkx and python-louvain are required: pip install networkx python-louvain
```

The call path is `index_chunks` → `_bind_stored_words` → `bind_word_taxonomy` →
`taxonomize_words` → `PrismRAG.ingest` → `build_communities`. PrismRAG declares
NetworkX and python-louvain under its optional `graph` extra, but cpu-llm requested
only its base package. Since this is a normal ingestion path, cpu-llm must request
that extra. The development environment already contained python-louvain, which
hid this missing dependency from the earlier live suite.

## Correction and verification

`pyproject.toml` now requires `prismrag-patch[graph]==0.2.1`. The existing PrismRAG
version is unchanged. A rebuilt wheel's dependency resolution installed the missing
`python-louvain==0.16` automatically; `pip check` then passed again.

The rebuilt wheel ingested all three records in a fresh database and passed:

- `What color is the Aster?` → `The Aster is blue.`, citing `smoke-color`.
- `What does the Aster have?` → the type membership and universal lens rule,
  citing both `smoke-type` and `smoke-rule`.

Both results were evidence quotations. The database server was stopped after
each live run. No production database was used. The tested dependency resolution
included Torch 2.15.0, sentence-transformers 6.2.0, Transformers 5.21.0, NumPy
2.4.6 and setuptools 84.2.1. This was a new dependency environment, not reuse of
the development virtual environment.

For an existing affected install, the immediate workaround is:

```powershell
python -m pip install "prismrag-patch[graph]==0.2.1"
```

## Other findings and limits

- A deliberately unavailable PostgreSQL endpoint reproduced
  `cpu_llm.access.StorageError: the database schema could not be opened`, chained
  from connection refusal. PostgreSQL/pgvector is a separate runtime prerequisite;
  a successful pip installation does not create that service.
- Public PyPI version 1.9.1 and Git use the same version string but contain
  different code. The public wheel lacks the newer `semantic.py` module and
  optional reference extras. The packaging correction needs a new release before
  a plain PyPI install includes it; no release was published by this audit.
- The optional Coreferee/spaCy dependencies resolved on this platform in a dry
  run. Their models and real backend were not executed here.
- Encoder loading used the existing shared Hugging Face model cache with offline
  mode enabled. This does not validate first-time model downloading or operation
  without model assets, nor does it cover Linux, macOS or other Python versions.
- Initial restricted-runner Temp/network permission errors were resolved using a
  workspace Temp directory and permitted public dependency downloads. They are
  audit-environment restrictions and are not attributed to the package.

Local evidence is retained in `build/clean-install-audit/`: source snapshot,
original/fixed build logs and distributions, install reports, import logs,
`live-smoke-before-fix.json`, and `live-smoke.json`. These are ignored local
artifacts. The smoke script uses a guarded `main()` for Windows multiprocessing.
