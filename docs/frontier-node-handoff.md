# Frontier Node — Coding Agent Handoff

For: the Claude Code session on `insightitsGit/cpullm`. From: Amin Parva. Companion to the design doc "Frontier Node Design — CPU-LLM" (draft 1, saved as `docs/frontier-node-design.md`). Save this file and the design doc under `docs/` in the repo before starting.

Source: https://claude.ai/artifact/E9vkvW9EFGc4meYFfBiu15

## Your task

1. Read the current code on `main` first. The design was written against PyPI 1.14.0, which is a few commits behind. Where the code differs from the design, follow the code's existing patterns and note the difference in your report.
2. Implement the Frontier node as described in the design doc.
3. Run the full existing test suite to confirm nothing regressed.
4. Build an AI-bottlenecks corpus, ingest it, run Frontier on it, and record the results.
5. Write a report and commit everything on a new branch. Do not merge to `main`.

## Step 1: Study the existing code

Before writing anything, read and summarise in your report:

- How the Research route runs Invention, source hypotheses and Nammade in parallel, then the abductive bridge.
- The abductive bridge node and its `UNVERIFIED_HYPOTHESIS` and `promotion: blocked` contract.
- Relationship-loop search (`cycle_search`) and its round, time, memory and edge budgets.
- Where deductive checks live (rule answers, Constraint Check, CrossDomain) and any inductive or pre-thinker logic on `main`.
- How prompt triggers map to nodes (`prompt-flag-map.md` and `.json`) and how `routing.executed_nodes` records execution.

Reuse these pieces. Do not duplicate them.

## Step 2: Implement Frontier

Requirements:

- **Triggers:** `Frontier: <topic>.` in chat, `frontier=True` in `Appliance.ask`, and `"frontier": true` on HTTP `/v1/ask`. Add them to the prompt-flag map.
- **Snapshot:** run against one authorized snapshot, the same way the research routes do.
- **Generation:** enumerate candidate relation combinations across related words and chunks, without preference pruning. Stream them in batches so the full set is never held in memory.
- **Filters, in order:** abductive check, deductive check (which also produces a relevance score), then a pre-thinker validation that rejects malformed, circular or trivial restatements.
- **Scores:** every survivor gets `source_support`, `deductive_relevance` and `novelty`, each from 0 to 1. Rank by source support, then relevance, then novelty. Document the formulas you choose.
- **Output:** 10 to 50 hypotheses, hard cap 50. Report a shortage instead of padding. Each entry has the hypothesis text, cited source IDs and quotes, the three scores, and a falsification test.
- **Contract:** every hypothesis stays `UNVERIFIED_HYPOTHESIS`. Never promote it and never write it into the index. Append the standard invention note. Strict evidence mode disables Frontier.
- **Budgets:** round, time, memory and candidate-count limits, configurable like `cycle_search`. If a budget stops the run early, set an `incomplete` flag and say so in the reply.
- **API field:** expose the results as `frontier` in the result dictionary, with `status`, `hypotheses`, `candidates_generated`, `candidates_passed` per filter, `budget_used` and `incomplete`.

Add unit tests for each filter, the scoring, the cap, the shortage report, budget stops, and strict-mode bypass.

## Step 3: Regression check

Run the full suite with `python -m pytest` against a disposable PostgreSQL/pgvector database. Every test that passed before your change must still pass. Record the before and after pass counts in the report. If an existing test fails, fix your code rather than the test, unless the test is wrong, and explain why.

## Step 4: AI-bottlenecks end-to-end test

**Build the corpus.**

- Gather public, freely licensed or openly accessible material on AI bottlenecks: compute and chips, energy and power, memory bandwidth, training data supply, algorithmic efficiency, cost, talent, and regulation.
- Prefer primary sources: research papers such as arXiv preprints, technical reports, and official industry or government publications.
- Aim for at least 50 documents across those subtopics. Save them under `tests/fixtures/ai_bottlenecks/` with a `SOURCES.md` listing each title, URL, date, and licence. Skip anything whose licence does not allow it.
- **Holdout set:** pick 5 to 10 known findings from the material, write them down in `holdout.md`, and remove the passages that state them directly before ingesting. This tests whether Frontier can rediscover them.

**Ingest and run.**

- Ingest into a dedicated namespace, `ai_bottlenecks_frontier`.
- Run `Frontier: AI bottlenecks.` and at least three narrower prompts, for example `Frontier: AI energy bottlenecks.`
- Run each prompt three times to measure variation between runs.
- Save raw results, timings and budget usage under `docs/reviews/<date>-frontier/`.

**Evaluate and report.**

- How many candidates were generated, and how many passed each filter.
- The top 10 hypotheses per prompt, with their scores and citations.
- How many holdout findings were rediscovered, fully or partially.
- Hypotheses that look wrong, trivial or unsupported, with your reasons.
- Run-to-run differences, timings on this machine, and memory use.
- Known limits and suggested next steps.

## Step 5: Deliver

- Commit on a new branch named `feature/frontier-node`.
- Write the report to `docs/reviews/<date>-frontier/report.md`.
- Update the design doc's open questions with the decisions you made.
- Stop and ask me before merging, publishing to PyPI, or changing any existing node's behaviour.
