# Prompt-triggered document tone: actual run

Prompts (no Python style argument):

- Write a detailed article about Helios in a friendly tone.
- Write a detailed report about Helios in a friendly tone.

The fresh database-backed appliance ingested the twelve original fictional Helios records and two Aster distractors. None of the records contains “friendly”. Both prompt-only requests generated new prose through `stylistic -> style_verify`. All twelve source claims passed the document inverse grammar, all original source quotations/hashes were retained, and the distractors were excluded. The word “friendly” was treated as a presentation control and removed from topic retrieval.

Read [the generated article](article.md) or [the generated report](report.md). The complete JSON preserves generated sentences, original quotes, per-sentence source IDs, lexicon score components, verification and the canonical quotation view.

The full suite passed 890 tests, skipped 56 optional tests and retained 3 existing expected failures (six existing NumPy overflow warnings). After prompt-planning refinements, 101 focused/live checks passed. A final case-insensitive topic refinement passed all 18 document-tone regressions. Receipts are included. This is an engineering example on fictional sources, not a claim of independently validated source truth or arbitrary prose coverage.

The run used a working tree based on revision 5766172, not a clean new release. The receipt captures the runner and files present at capture time; final-runtime-hashes.json separately captures the resulting runtime after the last case-insensitive topic refinement. The core example wording was unchanged by that refinement. The published 1.10.0 package was not rebuilt or changed.

Safety/coverage boundaries: strict evidence remains quotation-only. Unsupported/conditional/ambiguous records remain literal quotations. The grammar preserves source predicates and supports additive conjunction, limited contractions and explicitly licensed same-subject pronouns. It cannot invent missing architecture, establish source truth, or produce arbitrary expressive prose. Prompt parsing is explicit rather than inferred from the user's emotional state. Tone is per-request, with API settings overriding prompt directives.
