# Changelog

Release notes for each version are in [docs/releases](docs/releases). This file summarizes what each release added,
so the README can describe the current version only.

## 1.15.0

- **Frontier node.** `Frontier: <topic>.`, `frontier=True`, or `"frontier"` on `/v1/ask`.
  - Returns 10 to 50 ranked, cited `UNVERIFIED_HYPOTHESIS` entries built from relation combinations across one
    authorized snapshot.
  - Each candidate passes abductive, deductive and pre-thinker filters.
  - Each entry carries source-support, relevance and novelty scores, and a falsification test.
  - Budgets cover rounds, candidates, edges, memory and time.
  - Relevance is scaled by term specificity, and no single term may fill the top of the list.
- **Deepen node.** `Deepen: <hypothesis>.`, `deepen=<hypothesis>`, or `"deepen"` on `/v1/ask`. Checks one hypothesis
  link by link and returns supporting and contrary evidence, predictions, existing setups, confounders and a test
  plan.
- **Frontier checks its leading entries with Deepen** (five by default; `deepen_top` sets 0–10), and contested
  entries are flagged.
- **Natural-language routing.**
  - "What unexplored connections exist around X?" and "What don't we know about X?" go to Frontier.
  - "Check this hypothesis: …" goes to Deepen.
  - "Deepen idea N" works as a session follow-up.
  - These forms apply only when no existing specialist claims the prompt.
- **Dependency-parsed relations** when the `prompt_nlp` extra and a spaCy English model are installed, with an
  encoder cosine check on head-noun bridges.
- **Grounded inference expansion** (after 1.14.0):
  - deduction shared across research, Nammade and CrossDomain;
  - temporal, inductive and abductive analyses over selected JSON records;
  - clarified source-only APIs and evidence contracts.
- **Documentation.** The README is restructured for users and agents; `AGENTS.md` and
  `docs/agent-tool-schema.json` are added.

## 1.14.0

- Research routes as a literature-synthesis layer:
  - Innovation, hypothesis generation and the Nammade comparison run in parallel on one snapshot;
  - each reading is listed as its own option;
  - the reply explains why an option abstains or states an unverified hypothesis.
- Abductive bridge for disjoint stored bounds on one observable that differ on a named regime variable.
- Nammade scans (`Nammade: <topic>`, `nammade=True`).
- Evidence panel and executable research workspace (`Appliance.run_research_test`).
- Opt-in PrismLexicon vocabulary adaptation (`prismlexicon=True`, `target_level`).
- Grounded deductive inference with replayable proofs (`Infer whether …`, `inference={...}`).

## 1.13.1

- Request handling:
  - shared questions are split into cited lookups;
  - presentation instructions are separated from fact lookup;
  - evidence is searched before clarifying explicit factual requests.
- Direct measurements, color checks, exact location quotes and possession joins keep their source evidence.
- Conservative, corpus-backed spelling repair.
- Optional external LLM fallback, off by default, labelled `external_unverified`.
- Service operations: credential reload at authentication time, optional mutation audit (`--audit-db`).
- The revised synthetic request benchmark passed 460/460 rows at `7adf319`. See the
  [benchmark validity review](docs/benchmark-validity-review.md#recorded-results).

## 1.13.0

- Chunk inventory (`How many chunks …`, `app.chunk_inventory`, `/v1/chunks`).
- Confirmed single-chunk deletion (`app.delete_chunk`, `/v1/delete-chunk`) and team `admin` / `reader` roles.
- Parallel ingestion encoding (`encoder_workers`, 1–4).

## 1.12.x

- Research planning for document requests, with long-response targets.
- Bounded relationship-loop search (`Show relationship loops for X`, `cycle_search`).
- Taxonomy-driven invention with session follow-ups (`Invention: X`, `invent=True`).
- CrossDomain joins across knowledge-base prefixes, and Constraint Check for intervals.
- Numerical constraint scans (`scan_leptogenesis`, `evaluate_invention_constraints`).

## 1.11.2

- Learned writer fallback requires `CPU_LLM_ALLOW_LEARNED_WRITER=1`.
- HTTP bodies are capped at 1 MiB with a 10-second socket inactivity timeout.
- Child-safety compatibility warnings.
- Exact bare-number equivalence in strict conflict checks.
- Source run: 925 passed, 56 skipped, 3 expected failures. See the
  [1.11.2 build validation](docs/releases/1.11.2-build-validation.md).

## 1.11.1 and earlier

See [docs/releases](docs/releases) and the [release provenance](docs/release-publishing.md).
