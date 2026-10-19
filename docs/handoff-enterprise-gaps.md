# Handoff: enterprise gaps that still need a design

**ID:** HO-cpullm-003  
**Date:** 2026-10-18  
**Baseline:** `fdb4d78` on `main`, plus the source-delete, cued category list, and uncovered-decision reply in the working tree if those are not committed yet.  
**Status:** Problems stated. Solutions are not chosen.  
**Audience:** An agent who will design these gaps and then implement the design.

## Assignment

Design, then implement, the gaps below. Read the cited files before choosing a design. Do not reopen the three items already specified at the bottom of this document.

This is a single-process library. One `Appliance` indexes text into one PostgreSQL + pgvector database and answers on a CPU. A pilot on one corpus can use that. The gaps here are what still blocks a product used by more than one customer.

## Constraints that stay in force

* Python 3.11 or newer. Do not add a GPU decoder, a cloud chat client, or a general unconstrained language model.
* Do not relax `EpistemicEntailmentAuditor` or the PrismManifest span checks.
* Do not add `Modality.POSSIBLE` or `Modality.CONJECTURAL`.
* Do not route `imagine` between `think` and `cognize`. Think still edges directly to cognize.
* Do not synthesize propositions from `{category}:{term}` tags.
* Do not add neural coreference, spaCy, coreferee, or a bilinear `M_rel`.
* Do not invent policy, `ObjectiveSpec`, causal edges, or propositions from prose.
* Do not edit the installed VectorPrism, PrismCortex, or ChorusGraph packages. Extend this repository.
* Child safety and the fact-bridge `verify()` step stay off the answering path.
* The default tenant string stays `cpu-llm` unless the caller passes a namespace.
* WikiText text stays CC BY-SA 3.0 and GFDL. This code stays Apache-2.0.
* Do not invent latency or corpus-size numbers. The only measured question times are the 13 October 2026 table in the README, and they predate the rule-wording models.
* A labelled answer score is not retrieval recall. The last labelled run was 102 of 104 exact, 2 safe misses, 0 confidently wrong, with the passages handed in. The two misses are the parking-van case, answered `CONTESTED` while the old label said `UNKNOWN`. Leave that verdict as `CONTESTED`.

## G1 · Tenant boundaries

**Problem.** Two customers cannot share one deployment without seeing each other's text.

**What exists.** `Appliance(..., namespace="acme")` slugs the name and points PostgreSQL `search_path` at `ns_acme, public` (`_namespace_dsn` in `src/cpu_llm/pipeline.py`). The local ChorusGraph folder is `.chorusgraph/cpu-llm/<namespace>/`. That is a schema split, not a tenant product.

**What is still one tenant.** The graph store is constructed with `tenant_id="cpu-llm"`. The turn state writes `"tenant_id": "cpu-llm"`. The Chorus graph id is `appliance` under `cpu-llm`. Format nodes and `format_sense_cache` use that same tenant. PrismRAG in `word_taxonomy.py` and `catalog.py` is hardcoded to `cpu-llm`. Stage 5 of `docs/cpu-llm-v1.8-semantic-memory.md` says the tenant remains the fixed string `cpu-llm`.

**Design has to answer.** Whether a namespace is the tenant id everywhere, how a request selects it, and how a missing or unknown namespace fails. A design that only sets `search_path` and leaves the graph tenant as `cpu-llm` does not isolate memory.

## G2 · Access control

**Problem.** There is no caller identity and no rule for which sources an identity may read or write.

**What exists.** `PrismGuard` checks the prompt text. It does not know who is asking. `ingest` will store any file the process can read. `ask` searches the whole index.

**Design has to answer.** Where an identity is supplied, how a source is labeled with who may read it, and what `ask` returns when every matching passage is forbidden. Forbidden text must not appear in the quoted passage, the preface, or a document draft.

## G3 · Corrections

**Problem.** A customer cannot replace one stored fact and keep a record of the old wording.

**What exists.** Ingesting the same source again deletes vector rows for that id prefix and writes the new paragraphs (`save_chunks(..., replace_prefix=)`). PrismCortex `Operation.ACCOMMODATE` invalidates an edge and adds a replacement. This appliance does not use that operation for a corrected sentence. `Operation.PRUNE` only sets `valid_to` on an edge. It does not remove a node.

**Design has to answer.** What a correction identifies (one document id, one sentence, one role), what the reply says while two wordings exist, and what is retained for audit. Do not treat a full-source delete as a correction. Source delete is specified separately below.

## G4 · Authenticated API

**Problem.** The only interface is `Appliance.ask` and `Appliance.ingest` in-process. There is no HTTP service and no credential check.

**What exists.** Nothing listens on a port. Upload is a Python call.

**Design has to answer.** The routes, how a credential maps to the tenant from G1, and how a failed credential is refused before retrieval. A local unauthenticated wrapper around `ask` is not this gap.

## G5 · Concurrent asks

**Problem.** One question runs on the calling thread. A second question waits inside the thinker lock.

**What exists.** `src/cpu_llm/scale.py` `EngineManager` counts engines, places a seat on this server or another, and can send a ChorusSpine frame with the chunk id and the byte sizes. `WarmEvaluatorPool.run` holds one lock across the five thinker heads for the whole turn. `Appliance.ask` does not call `EngineManager` and does not start a second pool. The README states that the next release is the one that serves concurrent questions.

**Design has to answer.** How a second `ask` is queued onto another engine without sharing the thinker lock, what the frame carries (it must not pretend the 64-wide slot is the 1024-d tensor), and how a failure on the other seat is reported. Wiring `ask` straight to `EngineManager` without that design will run two turns on one locked pool.

## G6 · Memory stages 2, 3, and 4

**Problem.** Event memory answers who, where, and color for one round-tripped clause in the retrieved shortlist. It does not answer negation, a condition, or the same person named in two documents.

**What exists.** Stage 1 is `src/cpu_llm/memory/frames.py`, schema `stage1-v2`. `docs/cpu-llm-v1.8-semantic-memory.md` lists stages 2–5 as not built. Stage 5 overlaps G1 and G3.

**Design has to answer.** Stage 2: how negation, a condition, and uncertainty stay on the span and how an unsupported question is refused. Stage 3: how one entity id survives two sentences without a neural coreference model. Stage 4: how a role is found when retrieval did not return the sentence. Each stage needs the labeled acceptance set described in that design doc. Do not start stage 4 by embedding-nearest edges.

## G7 · Retrieval proof on a customer corpus

**Problem.** Nobody has measured how often the right passage is the one retrieved. The 102/104 figure is a wording score with the passages already chosen.

**What exists.** Search is VectorPrism, dense core `[16:384]`, HNSW `ef_search` 400, then a dense-core re-rank, `top_k` 5. The pipeline tests that construct `Appliance` against Postgres did not run on 18 October 2026. All 17 errors were `psycopg` connection timeouts to `localhost:5433` before the test body. Docker Desktop was not running. The record is `docs/test-results-2026-10-18.md`.

**Design has to answer.** The labeled set (question, relevant document ids, irrelevant neighbors), the metric (recall at 5, and whether the spoken answer used a relevant id), and the minimum result that would accept a customer corpus. Re-running the 17 tests is operational: start Docker Desktop, start `cpullm-pgvector` on port 5433, then `python -m pytest tests/test_pipeline.py tests/test_upload.py --tb=short`. That rerun is not a retrieval-recall study.

## G8 · Operations

**Problem.** There is no hosted install, no retention rule, and no support boundary.

**What exists.** A process, a local Postgres, and a sqlite graph under `.chorusgraph/`. `python -m cpu_llm.scale` prints a byte count for this machine. It is not a capacity contract.

**Design has to answer.** What is retained, for how long, who operates the database, and which failures the caller can see. Do not invent an uptime or a throughput number.

## Already specified

Do not redesign these. They are implemented, or they are being implemented, in this tree:

* A decision question (`can` / `could` / `may` / `why` / `allowed` / `required` / `permit`, see `_DECISION` in `src/cpu_llm/answering.py`) whose retrieved passages produce verdict `NONE` is spoken as `The retrieved passages do not settle that.` A definition question with no rule still quotes the retrieved sentence.
* The seven category sentences in fact-bridge `_MEMORY` are appended only when the retrieved text already contains that cue. `A laptop is a computer.` may follow `A MacBook Pro is a laptop.` when the MacBook sentence was just added. The London and premium-economy joins stay cue-based.
* `Appliance.delete_source(source)` removes one source's pgvector rows, the graph nodes whose ids start with that source prefix, and those document ids in the word index. The resonance ledger and `word_relations.json` are not rebuilt. A design for a full right-to-be-forgotten that includes those two ledgers belongs with G3, and it must not claim the current delete already does it.
* A misspelled question word is rewritten only from the stored chunk vocabulary, before `encode_query` and the later stages. The score is the cosine of character-pair and character-triple vectors. The floor is 0.45 and the gap to the next candidate is 0.05, measured in `src/cpu_llm/typos.py`. A stored word is not replaced. `result["typos"]` lists each rewrite. Do not turn the child-safety normalizer on, and do not switch this comparison to the retrieval encoder's cosine.

## Acceptance for any design you add

* A test shows the failure the design forbids, then the behavior the design requires.
* A second customer's text is absent from the first customer's reply, including preface and drafts, if the design touches G1 or G2.
* An unsupported memory question is refused. It is not answered from a nearby sentence.
* No new latency figure is written into the README unless you measured it on a named machine and recorded the command.
