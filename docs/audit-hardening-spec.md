# Audit hardening: source changes after 1.11.1

These changes are on `codex/audit-runtime-hardening`; the published 1.11.1
artifacts are unchanged. No release, upload, tag or repository setting is changed.

## Applied changes

- `Appliance` warns when explicitly asked to apply child-safety controls or a
  grade. These compatibility arguments do not apply the standalone gate.
  Invalid nonboolean safety flags are rejected. The standalone gate remains
  unvalidated; its former integration instructions have been corrected.
- Automatic learned writer fallback is disabled by default. Setting the process
  environment variable `CPU_LLM_ALLOW_LEARNED_WRITER=1` explicitly enables the
  existing fallback when compatible assets and decision/rule cues exist.
  This is not a verification guarantee. Strict evidence bypass remains unchanged.
- Strict scalar comparison treats bounded bare decimal representations as
  numerically equivalent and recognizes explicit mass/volume unit names.
  Original quotations and all proofs remain intact. Different dimensions,
  qualifiers, negation, precision differences and arbitrary case variants are
  not collapsed. Parsing of facts and question grammar is unchanged.
- HTTP request bodies are limited to 1 MiB. Negative/oversized lengths,
  duplicate Content-Length, Transfer-Encoding, truncated bodies and invalid
  UTF-8 are rejected. Socket reads time out after 10 seconds; body timeouts
  return 408. Header timeouts close the connection through the stdlib handler.
  This is an inactivity timeout, not a total request deadline or compute limit;
  slow trickle traffic and long engine work still require gateway controls.
- PyPI description source prominently separates Apache-2.0 code from bundled
  WikiText-2 CC BY-SA 3.0/GFDL data. Existing uploaded metadata is unchanged.

## Deliberately excluded

No broad case folding, general synonym equivalence or automatic sentence splitting
was added. These could erase qualifiers or create false agreement. Payment extras,
standalone strict packaging, adapters and wider grammars require separate designs
and were not treated as proven defects. Historical/repaired release findings were
not reapplied. No PyPI yank or additional release was performed.

## Verification

Run from the repository with loopback socket access:

```shell
python -m pytest -q -o addopts='' tests/test_audit_hardening.py tests/test_strict_evidence.py tests/test_strict_evidence_v2.py tests/test_http_thread_ownership.py tests/test_http_schema_contract.py tests/test_child_safety.py --junitxml=build/audit-hardening-tests.xml
```

Tests cover opt-in fallback, ambiguous distinctions, exact scalar equivalence,
proof retention, rejected body framing, a slow body followed by a successful
client, existing serial SQLite ownership, schema and strict fail-closed behavior.

Result: **72 passed in 21.27 seconds** on the maintainer's Windows/Python 3.12
environment. The initial sandbox run blocked loopback clients with WinError
10013; the recorded successful run used permitted loopback access.
