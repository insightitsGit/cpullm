# Default conversation integration validation

The complete live suite passed **891 tests**, with 2 skipped, 3 pre-existing
expected failures and 6 existing NumPy overflow warnings, in 115.15 seconds.
The new disposable database was `conversation_1102`, PostgreSQL 18 on Windows,
with cached encoder/parser assets and offline model settings. PostgreSQL was
stopped afterward. Raw local log: `build/conversation-tests.log`.

Coverage includes nine pure-turn forms, quoted/substantive nonmatches, original
application identity, typed strict social responses, full raw-prompt guard and
tenant checks, disable precedence, prefix provenance/offsets, preservation of
medication questions, controlled variants and relationship-risk fallback,
candidate source filters, noncommercial acknowledgment, real HTTP defaults and
server disable, and real source-scoped strict retrieval with a private
conflicting alternative. Existing financial, medical, tone and source-scope
regressions remain part of the full suite.

An initial focused run had 44 passing tests and three temporary-directory setup
errors in the restricted host environment. Setting TEMP/TMP to the workspace
resolved the fixture errors; the focused rerun passed 47/47 and the full live
suite above passed. No application workaround or disabled test was used.

Packaging verification built the wheel offline with no dependencies/build
isolation, then inspected the archive: `cpu_llm/conversation.py` and
`cpu_llm/data/conversation-pack.json` are present with 8 intents and 51 phrases.
The first wheel attempt hit the same host temporary-directory permission issue;
the workspace-TEMP retry succeeded. Local log:
`build/conversation-wheel-retry.log`.

No external dataset answers were downloaded, trained, ingested or redistributed.
The three supported dataset formats feed an explicit local review queue only.
Source cards were checked for declared licenses; an input file's claimed origin
is not independently authenticated by the importer. Clinical source truth and
clinical sign-off remain unverified.

After adding the explicit disabled-node list to the strict social receipt,
50 focused conversation, strict-mode, numeric and actual HTTP checks passed.
The [committed-runtime live demo](../../examples/2026-11-02-conversation/TRANSCRIPT.md)
then passed all 12 routing/status checks. The archived records retain actual
outputs and input/runner/pack hashes. An isolated wheel target install also
loaded the packaged conversation module/data and returned the expected identity;
the host's existing dependencies were reused, without a model constructor.
