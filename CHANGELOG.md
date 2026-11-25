# Changelog

Release notes for each version are in [docs/releases](docs/releases). This file summarizes what each release added,
so the README can describe the current version only.

## Unreleased (Frontier/Deepen v2)

Specified in [docs/frontier-deepen-v2-spec.md](docs/frontier-deepen-v2-spec.md), from the quantum computing audit.

- **Artefact filter.** Section headers, figure labels, author names, words merged by text extraction, meta nouns
  and bare comparator quantities no longer become hypothesis terms or candidate controls (`pre_thinker:artefact`).
- **Composition gate.**
  - Every Deepen receipt and Frontier check carries `lead_status`.
  - Contradictions that rest only on differently worded terms become `bridge_mismatch` instead of `contested`.
  - Contested and meaning-mismatched leads get a `resolve_first` plan instead of an experiment.
- **Coverage gaps.** Weak or missing links report document coverage. Thin coverage gives `coverage_gap` and an
  `add_sources` action.
- **Variable types.** Terms are typed as intervention, observable property, noise channel or outcome metric.
  Fixed properties and noise sources route to stratified or observational designs instead of a 2×2 factorial.
- **Suggested procedures.** Plans list cited setups that measure each variable, labelled not validated.
- **Frontier options.**
  - `screen` drops generic entries, re-ranks by relevance and novelty, and checks a shortlist with the novelty
    review.
  - `axiom_sources` marks background sources.
  - `topic_match` reports topic drift.
  - With checks requested, generation reserves 20% of the time budget for them.
- **Free-form Deepen.** Plain forms such as "A may reduce C", "A limits C via B" and "C may grow exponentially
  with A" are read, with a one-link `direct` pattern.
- **Prior art (opt-in).** `cpu_llm.literature_arxiv.ArxivReviewer` searches arXiv. The novelty review reports
  `prior_art_status`, which is never a finding.
- **Scale warnings.** Adjacent links at time scales 1,000× apart, or two abstraction levels apart, are flagged
  for review.
- **Ingestion speed.**
  - Relation edges stay in memory between ingests: about 14% faster per document on a 3,369-chunk knowledge base.
  - `ingest(..., consolidate="end")` consolidates once per call: about 3.4× faster for folders. It is opt-in.

## 1.16.0

- **Deepen research review.** Annotates each hypothesis without changing Frontier's candidates, ranking or limits:
  - semantic bridge warnings when linked terms change modifiers or meaning ("low weight decay" vs "increasing
    weight decay");
  - a `composition` assessment separate from per-link support, plus an interaction status;
  - operational test plans with user-supplied definitions, levels, units and protocol, `readiness`, and a list of
    `research_actions`;
  - candidate-control roles (outcome predictor, shared cause, downstream), never adjusted automatically;
  - cited source conditions and context;
  - progressive "Go deeper" follow-ups;
  - an optional novelty review that reports overlap in the knowledge base (`deepen={"hypothesis": ..., "novelty": True}`),
    with an operator-registered literature reviewer that is off by default.
- Deepen accepts an envelope: `deepen={"hypothesis", "definitions", "protocol", "novelty", "external_review"}`.
- Frontier/Deepen correctness fixes (direction across every link, negation semantics, shared request budget).
- Install the newest source with `pip install "git+https://github.com/insightitsGit/cpullm@main"`.

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
