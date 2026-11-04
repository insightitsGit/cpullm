# Launch-readiness review response

The public review identified real presentation and release-discovery gaps.
The README now leads with published 1.11.1, setup requirements, evidence limits,
licensing and one scoped test count. The longer implementation reference remains
available separately. Current website whitepaper links replace the historical
PDF in the entry page. Finance precision wording now matches the explicit
six-place policy rather than an older two-place pilot.

The 56 test skips are explained in `docs/testing-results.md`: 54 opt-in integration
cases were disabled and two extractor checkpoints were unavailable. Historical
benchmark counts remain historical records. Container execution is still open;
configuration validation and native PostgreSQL smoke are distinguished.

Published distribution hashes were checked against the publication receipt.
All 108 wheel Python files match commit `c2de454` after newline normalization.
The matching GitHub tag/release uses that implementation commit. No package
artifact was rebuilt or uploaded during this documentation update.

Code and bundled-data licensing are prominent and separated. The consolidated
notice is included in future source distributions; existing 1.11.1 artifacts
already contain dataset provenance and remain unchanged.

Two open Dependabot PRs update pip/pytest only in the historical October 29
benchmark lockfile. They are not runtime fixes and were not merged or closed.
No priority or superiority claim over VerbatimRAG or other systems is made.

Remaining owner/host actions:

- Decide whether to yank 1.11.0; recommend 1.11.1 for HTTP meanwhile.
- Configure the PyPI Trusted Publisher and GitHub environment before using the
  manual future-release workflow. Existing manual uploads are not attested.
- Verify Docker container startup on a functioning Docker host.
- Published PyPI long-description wording remains the uploaded release text;
  repository corrections apply to future builds.
- Independent clinical, customer-corpus and hosted-model comparisons remain
  unrun. Fixture results do not establish those outcomes.
