# Review of 9d6fbe8

Reviewed on 19 October 2026, America/Los_Angeles, against 1183b77. No new actionable findings in this commit's production-code changes.

Both prior findings are fixed:

- The UNKNOWN branch now unpacks all five opinion fields. The exact missing-duration reproduction returns UNKNOWN through `fact_bridge.answer`, and the live Appliance returns a complete reply asking for duration instead of a partial graph result.
- Entity extraction preserves internal words. Live questions about Bank of America and Research and Development return their ingested facts. Ada remains supported, and the harbor-kestrel reply excludes the unrelated picnic sentence.

Verification completed:

- **126 targeted tests passed, 1 fixed-ID database test deselected.** The same fourteen-file suite from the previous review was rerun, including the new regression tests. [Pytest transcript](pytest-9d6fbe8.txt).
- **Five live Appliance checks passed**, using a fresh namespace and a seven-paragraph controlled corpus. All returned complete replies without partial-result errors. The missing-duration case was also tested directly through the public fact-bridge function.
- `git diff --check 1183b77..9d6fbe8` passed.

[Executable live checks](review-9d6fbe8-probes.py) and [recorded inputs and outputs](review-9d6fbe8-probes.json) are included. The script asserts the expected outcomes and leaves existing corpus documents unchanged.

This was a targeted commit review. The full repository suite and the earlier 27-question timing benchmark were not rerun. No claim of complete repository correctness or production readiness follows from these checks. Production code was not changed during the review.
