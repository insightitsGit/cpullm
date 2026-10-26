# CPU-LLM baseline, 2026-10-25

Independent evaluation of `main` at `3d3c0543c8862c3961a32f6743d027623e32d0da`. No library code was changed. Nothing was committed or pushed.

## Source snapshot

```
git rev-parse HEAD
3d3c0543c8862c3961a32f6743d027623e32d0da

git status -sb
## main...origin/main
```

The tree was clean at the start. The only untracked path created for this report is `docs/benchmarks/`. `git status -sb` at the start of the evaluation, after the report directory existed, was `## main...origin/main` plus `?? docs/benchmarks/`. No other dirty files were present, so the run was not a mixed tree.

Recent commits on this snapshot: `3d3c054` (abandon a ranking when the next question repeats its subject), `48ac0ed` (scope isolation and unsupported question replies), `8d915db` (resonance tags). The handoff in `docs/reviews/2026-10-25/recent-commits-handoff.md` still describes uncommitted fixes after `8d915db` and a 459-pass run. That count predates `48ac0ed` and `3d3c054`. It was not reused as the current suite result.

Machine: Windows 11, Python 3.12.10, 24 CPUs, Intel64 Family 6 Model 198. Offline model loads: `HF_HUB_OFFLINE=1`, `TRANSFORMERS_OFFLINE=1`.

## Suite

Live Postgres did run. Docker Desktop was not running; it was started for this task. Disposable container `cpullm-bench-20261025`, image `pgvector/pgvector:pg16`, published on `127.0.0.1:5434`. The local PostgreSQL 18 service on port 5432 was not used. The container was removed after the runs.

Two suite executions:

| Run | Database setup | Result |
|---|---|---|
| First | Fresh `vectorprism` database. The extension was not created in `public` beforehand. The first namespaced appliance installed the relocatable `vector` extension into its own schema (`ns_join_audit_…`). Later namespaces could not see the type. | **4 failed, 443 passed, 2 skipped, 3 xfailed, 17 errors in 37.46s.** |
| Official | New database `cpullm_public` with `CREATE EXTENSION vector SCHEMA public` before pytest. | **1 failed, 463 passed, 2 skipped, 3 xfailed, 6 warnings in 61.96s.** |

The three expected failures are unchanged:

- `test_spread_does_not_merge_senses_through_an_accidental_shared_word`
- `test_bare_crane_is_ambiguous`
- `test_cluster_groups_stay_pure_and_unfragmented`

Skips: two tests that need a trained extractor checkpoint (`test_answering.py`, `test_fact_bridge.py`).

Warnings: six `RuntimeWarning`s, overflow in NumPy `multiply` and `dot` inside `numpy/linalg/_linalg.py`, raised from three pipeline tests (`test_supplied_homarus_proposition_is_realized`, `test_six_channel_nodes_quote_the_passages_and_suggest_discovery_for_a_why_question`, `test_numeric_facts_come_from_the_passage_and_the_causal_graph_comes_from_the_caller`).

The one failure in the official run is `test_live_correction_times_and_restart_keep_version_intervals`. The historical and current color answers in that test passed. The reopen then built `VectorPrismIndex` from `appliance.index.db.conn.info.dsn`. That DSN has user, host, database, and `search_path`, and it does not include the password. Connection failed with `fe_sendauth: no password supplied`.

Log: `pytest-full.txt`. The first attempt is `pytest-fresh-extension-in-first-namespace.txt`.

## Evaluation set

Thirty paragraphs written for this run: a Millhaven ferry manual (21), a separate ledger (3), and a town notes page that uses "spring" for a clock and for water (6). They are in `corpus.json`. They are not the resonance corpus, the lobster or harbor-kestrel fixtures, or the join-pipeline beetle and orchid sentences.

Each arm ingested those paragraphs with the same settings. Dense used `Appliance(..., resonance_tags=False)`. Resonance used `resonance_tags=True`. Forty-one turns per arm, including five two-turn scripts. A clarification is not scored as a factual answer. A similarity, a graph edge, or a resonance tag is not scored as proof.

Raw turns: `responses-dense.json`, `responses-resonance.json`. Automatic scorer output: `metrics-dense.json`, `metrics-resonance.json`. The headline below uses that scorer, with two corrections called out where the scorer and the reply contract disagree.

## Headline: dense vs resonance

| Metric | Dense | Resonance |
|---|---|---|
| Factual correctness | **14 / 18 (0.778)** | **7 / 18 (0.389)** |
| Wrong-answer rate | **4 / 41 (0.098)** | **3 / 41 (0.073)** after dropping one scorer false positive; automatic scorer said 3 / 41 including that false positive |
| Citation completeness | **14 / 15 (0.933)** of turns that answered | **7 / 7 (1.000)** of turns that answered |
| Retrieval precision / recall | **0.225 / 0.981** over 18 scored retrievals (2 excluded) | **0.253 / 1.000** over 10 scored retrievals (10 excluded) |
| Appropriate clarification | **6 / 7 (0.857)** | **7 / 7 (1.000)** |
| Appropriate abstention | **4 / 4** counting "No stored sentence names who did that."; automatic scorer **3 / 4** | **2 / 4 (0.500)** |
| Conversation completion | **4 / 5 (0.800)** | **3 / 5 (0.600)** |

Factual correctness is only turns whose expected outcome is an answer. Resonance's drop is almost entirely sense questions on ordinary Cedar questions. Those turns are not wrong answers; they are unanswered.

Wrong answers counted here are disallowed claims: an unsupported question that quotes stored sentences, or a reply that states a forbidden phrase and is not a clarification. The automatic scorer also marked dense "What does the Cedar have?" as wrong because it stated the true diesel-engine sentence and omitted the life raft. That one is an incomplete answer, not a false claim, and it is the citation miss. The automatic scorer marked the resonance "Who captains the Cedar?" turn as wrong because the sense-word list contained "diesel", "white", and "Millhaven". That is a clarification, not a claim that those words answer the question. Removing it leaves three resonance wrong answers.

### Factual correctness by category

| Category | Dense | Resonance |
|---|---|---|
| Direct fact (color, kind, where, alias) | 4 / 4 | 1 / 4 |
| Paraphrase ("colour", "kind of vessel") | 2 / 2 | 0 / 2 |
| Join (lifespan; possessions) | 1 / 2 | 0 / 2 |
| Definition | 2 / 2 | 2 / 2 |
| Corroborated spring queries | 2 / 2 | 2 / 2 |
| Scope-restricted color | 2 / 2 | 2 / 2 |
| Synonym ("town-operated") | 0 / 1 | 0 / 1 |
| Explicit ranking | 0 / 2 | 0 / 2 |
| Reference follow-up | 1 / 1 | 0 / 1 |

Retrieval precision is low because the scored set is passage ids plus related ids, and related rows include neighbors that are not the gold sentence. Recall of the gold ids inside that set is high on the turns that actually retrieved. Resonance excludes ten retrievals because it returned a clarification before search.

## What each arm did

**Dense answered the licensed attribute questions.** "What color is the Cedar?" quotes `millhaven-ferry-p0004`, "The Cedar is white." Kind, British spelling "colour", "kind of vessel", and "Where does the Cedar live?" do the same. "Where does the evening boat live?" quotes the place sentence and cites both the alias sentence (`p0015`) and the place sentence (`p0016`). "How long does the Cedar live?" quotes both "The Cedar is a municipal ferry." and "Every municipal ferry lives for 30 years." "What is a life raft?" and "What kind of craft is a life raft?" say it is an inflatable craft. "What is a clock spring?" quotes the town-hall clock sentence and not the water sentences. "What is a mountain spring?" quotes the mill-pond sentence and not the clock sentences.

**"What does the Cedar have?" did not join.** The reply is only "The Cedar has a diesel engine." from `p0003`. It does not cite the membership sentence or "Every municipal ferry has a life raft." The Larch questions did not copy that raft or the 30-year rule onto a tour boat. Both abstained with "The retrieved passages do not settle that."

**A frequent name becomes many senses when resonance is on.** "What color is the Cedar?", "What kind of boat is the Cedar?", "Where does the Cedar live?", "What does the Cedar have?", "How long does the Cedar live?", and both paraphrases return a sense question. The listed "meanings" are fragments of the manual (diesel/engine, Millhaven, white, dawn), not two senses of Cedar. "Cedar" occurs in seven manual sentences. Under the hub rule that is frequent enough not to carry activation, and a question whose only stored word is that hub is treated as ambiguous. "Rowan" is rarer, so "What color is the Rowan?" still answers. "What is a clock spring?" has two corroborating words and still answers on both arms.

**Bare "What is a spring?"** Resonance asks which meaning and does not store a pending choice (`pending` unchanged without a session). The choices separate clock words from water words, and they also list a Millhaven fragment. Dense does not ask; it abstains with "The retrieved passages do not settle that." It does not pick one sense. A following "1" with no session does not resume a choice on either arm. Pending keys are unchanged. The reply is the proposition withhold, not a selected spring sentence.

**Conflict, antonym, scope, block.** Both arms, unscoped, say the Rowan passages conflict and quote both "The Rowan is green." and "The Rowan is blue." "Is the night service open?" is answered with "The night service is closed." A caller limited to the ferry manual gets blue and not green or 4419. A caller limited to the ledger gets green and not blue. The annex-code question inside the ferry scope abstains and does not reveal 4419. An empty source list returns no Cedar sentence. Two overlapping scoped asks, one per source, each returned only that source's color. Both blocked prompts ("Ignore all previous instructions…", including the one that also says "spring") return "The prompt was blocked by PrismGuard." with no evidence ids, no passages, and no sense list.

**Ranking.** "Which ferry is best?" asks for a criterion on both arms. "how it rides" then asks for evidence. "cancel" cancels. "Which ferry is white?" sets `clarification_abandoned` and does not repeat the criterion question. "fuel economy", and the single question "Which ferry is best for fuel economy?", still ask for comparison evidence even though `millhaven-ferry-p0011` ("The Cedar is best for fuel economy among Millhaven ferries.") is in the retrieved passages. The topic check strips a trailing "s" once, so "ferries" becomes "ferrie" and does not match the topic word "ferry". The retrieved ranking is therefore not quoted.

**Reference.** Dense: "Where does it live?" asks which entity; "the Cedar" then quotes "The Cedar is found in Millhaven." Resonance asks the reference question, then the follow-up "the Cedar" is swallowed by the same Cedar sense split.

**Synonym.** "Is the Cedar town-operated?" is withheld on both arms: "The checked sentence was withheld because it did not match the stored proposition." The manual's own gloss, "Municipal means town-operated in this manual.", is not used.

**Unsupported shapes.** None of the four turns returned "This question type is not supported yet."

- "Why does the Cedar use a diesel engine?" quotes "The Cedar uses a diesel engine because the river current is strong." and repeats it under an Explanation heading. Both arms.
- "When does the Cedar depart?" does not say "dawn". It copies other Cedar sentences: found in Millhaven, municipal ferry, best for fuel economy, white, diesel engine. Both arms.
- "How many municipal ferries serve Millhaven?" lists the membership sentences, including Sable. Both arms.
- "Compare the Cedar and the Rowan." On dense, a Comparison section copies white, blue, best, and the diesel engine, and it also quotes the ledger's green sentence in the body. On resonance, the compare question is turned into a sense question instead.

**Missing captain.** Dense: "No stored sentence names who did that." That is an abstention; the automatic scorer did not recognize the wording, so it counted 3 / 4 instead of 4 / 4. Resonance asks a Cedar sense question instead of abstaining.

## Lifecycle, restart, and the 10,000th paragraph

| Check | Dense | Resonance |
|---|---|---|
| Two corrections; `as_of=1700010150` quotes grey; current quotes yellow; middle row `valid_to` is 1700010200 | Pass | Pass, and the live resonance tag id is only `marker-note-p0001-v1700010200` |
| Reingest dock bell white → red, delete it, neighbor flag stays green | Pass. After deletion the bell question is "That question is not in the supported event-frame form." and does not repeat white or red. | Fail as a reply check. Before and after reingest, and for the neighbor, the reply is the proposition withhold, so the color change is not visible in the answer. The delete receipt still reports `vector_rows: 1` and one resonance unit removed. |
| New appliance, same namespace | Cedar still white, buoy still yellow, flag still green, deleted bell not quoted | Buoy still yellow. Cedar is a sense question again. Flag and bell are withheld. |
| 10,000-paragraph source | Pass | Pass |

Both arms ingested `wideledger` and `wideledger-policy` through `chunks_for` ids and `catalog_chunks` in batches of 500 (the same id function `ingest` uses; batched so the run could record cost). The last ids are `wideledger-p10000` and `wideledger-policy-p10000`. A caller scoped to `wideledger-p` is answered from `wideledger-p10000` ("The wide ledger beacon is white.") and does not receive the policy paragraph. Deleting `wideledger` leaves only `wideledger-policy-p10000`. The policy-scoped question then quotes yellow and not white.

Scoped ask time at 10,000 paragraphs: dense **0.070 s**, resonance **8.779 s**.

## Cost and scale

Cold `Appliance` construction in this process: **5.848 s**. Later appliances in the same process opened in **0.64–0.77 s**. In-process working-set reads failed (`GetProcessMemoryInfo` returned 0), so memory below is the evaluation process working set from outside the script.

| Sample | Working set |
|---|---|
| During dense 10,000-paragraph ingest | about 1,293 MB |
| During resonance 10,000-paragraph ingest | 2,023 MB |

Gold corpus, 30 paragraphs: dense ingest **1.174 s**, resonance **1.253 s**.

Warmed "What color is the Cedar?" after 2 discarded calls, 20 samples:

| Arm | p50 | p95 | p99 |
|---|---|---|---|
| Dense (real color answer) | 0.053 s | 0.084 s | 0.111 s |
| Resonance (sense question, search not run) | 0.021 s | 0.026 s | 0.034 s |

The resonance percentile is faster because that question returns before retrieval. It is not a faster answer.

Clean scale namespace, question "What color is the scale probe token?" (answered with blue on every size):

| Paragraphs | Dense ingest | Dense ask | Resonance ingest | Resonance ask |
|---|---|---|---|---|
| 40 | 0.759 s | 0.102 s | 0.938 s | 0.134 s |
| 200 | 3.203 s | 0.071 s | 4.745 s | 0.186 s |
| 800 | 13.053 s | 0.061 s | 14.366 s | 0.150 s |

Ask latency is flat through 800 paragraphs. Ingest is a few tens of milliseconds per paragraph and slower per batch as the table grows. On the 10,000-paragraph load, a batch of 500 took about 8 s at the start of an empty arm and about 16–20 s for the last batches, with the second source slower because the first 10,000 rows were already stored.

| Source | Dense | Resonance |
|---|---|---|
| `wideledger` 10,000 paragraphs | 242.0 s | 230.5 s |
| `wideledger-policy` 10,000 paragraphs | 302.1 s | 323.0 s |

Full evaluation wall time, both arms plus scale: **1,189.5 s**.

## Failure patterns

1. **Resonance turns a repeated entity into a sense question.** Recognized color, kind, location, lifespan, and possession questions about Cedar never reach retrieval. Sense labels are nearby sentence fragments, including words from a single meaning. This is the largest accuracy gap versus dense.
2. **Unsupported why, when, count, and comparison do not use the fixed sentence.** They copy stored sentences. Why also adds an Explanation. Dense compare adds a Comparison section that mixes in the other source's color. When does not even quote the departure sentence; it quotes unrelated Cedar facts.
3. **An explicit ranking that was retrieved is not quoted.** `p0011` is the top passage for the fuel-economy ranking, and the reply still asks for evidence. "ferries" does not match the topic word "ferry" after one trailing "s" is removed.
4. **The universal "has" join is not spoken.** Lifespan cites membership and "Every municipal ferry lives for 30 years." Possessions stop at "The Cedar has a diesel engine." and omit the life-raft rule. A type link still does not copy ferry attributes onto the Larch.
5. **Fresh database setup and reopen.** The first namespaced call can install pgvector into that namespace schema, after which other namespaces fail. Reopening from `conn.info.dsn` drops the password. That is the only official suite failure.
6. **Cost grows with paragraph count, sharply for resonance asks.** Ingest batches roughly double from the first 500 rows to the last. A scoped ask over 10,000 resonance tags takes 8.8 s against 0.07 s for dense. Ask time through 800 paragraphs does not show that cliff yet.
7. **Some replies are a proposition withhold instead of a quote or a clear abstention.** "Is the Cedar town-operated?" does this on both arms. With resonance on, the dock-bell reingest and the dock-flag neighbor do it as well, so those color checks cannot be read from the reply.

## Improvement list

Not implemented.

1. If the question is a recognized attribute, definition, or relation, do not replace it with a sense question. A hub word that is the name of the entity should not split every sentence about that entity into a competing meaning.
2. For why, when, a bare how many, and a comparison, return only "This question type is not supported yet." Do not attach Explanation or Comparison sections made from other sentences.
3. Create the vector extension in `public` before any tenant `search_path` is set, and reopen with a DSN that still authenticates.
4. Quote a retrieved ranking sentence when it states the criterion. Match a plural topic to its singular.
5. When a membership sentence and an "Every … has …" rule are both authorized, cite both in the spoken answer, as the lifespan join already does.
6. Replace the quadratic sense-component step and keep ingest cost from climbing as the prefix grows. The 10,000-paragraph scoped ask is the measurement.
7. On a yes/no or a color question that the proposition check will not speak, abstain or quote the stored sentence. Do not leave reingest and deletion checks looking identical.

## Reproduction

Official suite:

```powershell
$env:CPU_LLM_LIVE_TESTS = '1'
$env:VECTORPRISM_PG_DSN = 'postgresql://vectorprism:vectorprism@127.0.0.1:5434/cpullm_public'
$env:HF_HUB_OFFLINE = '1'
$env:TRANSFORMERS_OFFLINE = '1'
$env:PYTEST_DISABLE_PLUGIN_AUTOLOAD = '1'
python -m pytest tests -ra
```

The database must already have `vector` in `public`. Creating the extension only through the first namespaced appliance reproduces the 17 errors.

Evaluation, from the repository root, same variables:

```powershell
python docs/benchmarks/2026-10-25-baseline/run_eval.py
```

That command recorded this directory. Repeating it now stops: pass `--out` as a new empty directory. The script refuses this baseline directory and any directory that already has files.

Disposable server used here:

```powershell
docker run -d --name cpullm-bench-20261025 -p 127.0.0.1:5434:5432 `
  -e POSTGRES_USER=vectorprism -e POSTGRES_PASSWORD=vectorprism -e POSTGRES_DB=vectorprism `
  pgvector/pgvector:pg16
docker exec cpullm-bench-20261025 psql -U vectorprism -d postgres -c "CREATE DATABASE cpullm_public;"
docker exec cpullm-bench-20261025 psql -U vectorprism -d cpullm_public -c "CREATE EXTENSION IF NOT EXISTS vector SCHEMA public;"
```

The container was removed after the evaluation.

## What this run did not do

- It did not edit the three expected-failure tests.
- It did not use the lobster, harbor-kestrel, beetle, orchid, or `tests/resonance_corpus.py` sentences as the gold set.
- In-process RSS was not available. Memory figures are two external working-set samples, not a full allocator trace.
- The 10,000-paragraph sources were stored with `catalog_chunks` in batches of 500 using ids from `chunks_for`. That is the id path `ingest` uses. It is not one single `ingest()` call, because a single call would not record per-batch time.
- No second official suite was run against the database where `vector` lived only in the first tenant schema. That result is the first row in the suite table.
