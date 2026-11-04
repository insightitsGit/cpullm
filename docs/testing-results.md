# Test results and scope

The recorded 1.11.1 source suite reports **905 passed, 56 skipped, 3 xfailed**
and six existing NumPy warnings. The receipt is
[`full-patch-tests.xml`](reviews/2026-11-03-public-artifact-audit/full-patch-tests.xml).
Its 964 cases include 59 XML skipped elements: 56 skips plus three expected failures.

Of the 56 skips, 54 are opt-in PostgreSQL/encoder integration cases for which
`CPU_LLM_LIVE_TESTS` was not enabled. Two require an optional trained extractor
checkpoint. These are unexecuted cases, not passes. Disabling the integration
flag does not establish that their dependencies were absent.

The expected failures concern crane-sense grouping (two cases) and finance
threshold grouping (one case). They remain known limitations.

Separate validation covered 19 HTTP service/schema/thread checks, installed-wheel
strict requests and ordinary requests from three clients, and 12/12 authored
healthcare demo outcomes. These are separate receipts, not additions to 905.
See the [release validation](releases/1.11.1-build-validation.md).

Run the default suite with:

```shell
python -m pytest -q -o addopts=''
```

Enable `CPU_LLM_LIVE_TESTS=1` only with the disposable database and cached assets
specified by the tests. No claim is made here that all 54 opt-in cases passed.
Older counts in benchmark records belong to their recorded revisions, flags and
environments; they are not the current release headline.

Docker Compose configuration was validated, but container execution remains
unverified because the maintainer's Docker Desktop host crashes before startup.
The installed-package database smoke used native PostgreSQL 18/pgvector.
