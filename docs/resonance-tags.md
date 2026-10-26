# Resonance tags: word-level resonance for retrieval (design + prototype)

Status: wired, 2026-10-25. Code: `src/cpu_llm/resonance_groups.py`.
Tests: `tests/test_resonance_groups.py`. Measured comparison: `python tests/resonance_eval.py`.
`Appliance(..., resonance_tags=True)` is the default. The store is
`resonance_tags.db`, maintained on ingest, delete, and correction. Recall adds
candidates; it does not write an answer. A tag that only shares a hub word is
not loaded. `word_tags.json` stays. Pass `resonance_tags=False` to keep the
previous retrieval.

## 1. The idea (owner's words, restated)

When a person hears a word, a wave runs through everything related to it. A word is
not linked to every word it ever met; it is linked through the **contexts** it
appeared in. "Bank" in a sentence about cops protecting assets from robbers is one
context. "Bank" in a sentence about a river shore is another. A query activates the
contexts its words share, so "bank police robbery" lights the first and leaves the
second silent.

## 2. Definitions (use these words exactly)

| Term | Meaning |
|---|---|
| **tag** | One ingested sentence. Its id is the tag id. All its content words sit inside it. |
| **word** | A normalized content word (3+ letters, light stemming, stop words removed). |
| **membership** | word -> many tags. A word has one tag per sentence it appears in. |
| **hub word** | A word frequent enough that it cannot tell contexts apart ("bank", "bat"). |
| **corroboration** | Two or more query words lighting the same tag. |
| **resonance** | Activation carried from lit tags through their non-hub words to other tags, with decay. |
| **sense** | A set of tags connected through shared non-hub words, directly or through one other tag. |
| **ambiguous** | A single query word whose lit tags split into two or more senses. |

Important: the earlier prototype clustered sentences into "groups" (`recall`). That is a
dead end for this corpus (section 6). The design is **tags plus spreading activation**
(`recall_spread`), with no clustering step. The cluster code is kept only for comparison.

## 3. Data model (SQLite, one file per namespace, same pattern as `knowledge_graph.db`)

```
unit(unit_id PK, doc_id, ord, text)            -- the tag; doc_id is the chunk id
unit_word(unit_id, word, tf)  PK(unit_id,word) -- word -> many tags (index on word)
grp(group_id AUTOINCREMENT)                    -- prototype clustering only; drop later
```

`doc_id` is the vector-table chunk id, so a recalled tag maps straight to a chunk that
`appliance.index.db.get_by_ids(...)` can load.

## 4. Algorithm (`recall_spread`)

1. Query words = content words of the message. Look up their tags (scoped, see section 7).
2. First hop: `first(tag) = (sum of idf of query words in the tag) * (number of them)`.
   The multiplier is the corroboration bonus.
3. If no tag is corroborated (only one query word matched, or none share a tag) split the
   lit tags into senses. Two tags are the same sense if they share a non-hub word, or a
   third tag shares a non-hub word with each (two hops). Two or more senses ->
   `status="ambiguous"`, no units, and a few words per sense for the host to show.
4. Otherwise carry activation from the best tags through their **non-hub** words, light
   the tags of those words with a decay (default 0.5), and keep every tag in the same
   sense component as the best tag. Return ranked tags with `expanded=True` for those
   that contain none of the query words.
5. Output is **candidates only**. It never writes an answer. Grounding, audit and
   abstention remain in charge of what is said.

Hub rule: a word is a hub when `df >= 4` and `df >= 15%` of tags. Hubs stay members of
their tags and still count as query words; they just never carry activation onward.
This is what stops "bank" from carrying police to the river.

## 5. Where it plugs into the existing pipeline

| Step | File / function | Change |
|---|---|---|
| Ingest | `pipeline.py` `Appliance.index_chunks` and `catalog_chunks`, next to `_bind_stored_words(...)` | `self.resonance_tags.add_chunks(chunks, replace_prefix=replace_prefix, consolidate=False)` |
| Delete | `source_delete.py::delete_stored_source` and `Appliance.delete_source` | `resonance_tags.delete_prefix(prefix)`; add its counts to the receipt |
| Correct | `Appliance.correct` | re-add the replaced sentence under the new id; drop the old tag |
| Recall | `pipeline.py::_retrieve`, right after `_with_tagged_paragraphs` | `recall_spread(message, allowed=allowed)`; load `chunk_ids` with `get_by_ids`, then `keep_allowed` (as `_with_graph_paragraphs` does) |
| Ambiguity | `clarification.py` | new slot `sense`: show `result.senses` words, send the user's pick back with the same `session_id` |
| Storage path | beside `knowledge_graph.db` under `.chorusgraph/cpu-llm/<tenant>/` | `resonance_tags.db` |
| Flag | `Appliance(..., resonance_tags=True)` | default on. `False` leaves retrieval as it was. Hub-only tags are not added to the passage list |

What it replaces or improves: today `_with_tagged_paragraphs` only recalls inside articles
already in the shortlist and only words the query typed (category = article, one hop,
exact word). `word_tags.json` is one global JSON file rewritten on every ingest. The new
store crosses articles, separates senses inside one article, and is a table, not a file.
Do not delete `word_taxonomy` until the new store beats it on a real evaluation set.

## 6. What the prototype measured (and what it did not)

Corpus: `tests/resonance_corpus.py`, 33 hand-written sentences, four ambiguous words
(bank, bat, python, crane), two senses each, all in ONE source with senses mixed inside
paragraphs. Synthetic and written by the module author. 17 multi-word queries.
Baseline: any sentence sharing a query word (a lexical strawman; the real pipeline's
dense retrieval already separates many of these, so do not read the gap as end-to-end).

| Method | Precision | Recall |
|---|---|---|
| Lexical baseline | 0.50 | 0.96 |
| Cluster groups (`recall`) | 1.00 | 0.64 |
| **Spreading tags (`recall_spread`)** | **0.88** | **0.89** |

- Bare "bank", "bat" and "python": spreading flags **ambiguous** and lists the senses.
  Lexical returns 6-8 mixed sentences. Bare "crane" is **not** flagged (below).
- All of spreading's lost precision is the four **crane** queries (0.50 each): the two
  senses are linked through the shared verb "lifted". Excluding crane, precision is 1.00.
  `test_spread_does_not_merge_senses_through_an_accidental_shared_word` is a strict xfail.
- **Clustering failed in both directions.** One join threshold fragments a sense into
  several groups (finance split in 5) or fuses senses (bat animal + bat sport merged)
  because the ambiguous word itself is the bridge. Ignoring hub words removed the fusing
  but not the fragmentation; no threshold gave both. Sweep on this corpus:
  merge threshold 0.22 -> pure groups but 5 finance fragments; 0.03 -> 1 finance group but
  3 impure groups. That is why the design uses soft spreading instead of hard groups.
- Not measured: real documents, embeddings, latency, memory, large `N`, concurrent
  ingest, anything about answer quality. 17 queries is a mechanism check.

## 7. Rules the implementation must keep

1. **Scope.** Count only tags whose `doc_id` is inside the caller's allowed sources.
   Statistics (df, idf, components) must be computed from in-scope tags only, so scores
   never reveal out-of-scope text. The prototype does this with an `in_scope` SQL
   function.
2. **Exact source boundary.** `hr-p` matches `hr-p0001` and `hr-p0001-v2`, never
   `hr-policy-p0001`. The prototype's `doc_in_source` is the helper proposed in
   `handoff-review-2026-10-25.md` item 1. Use one shared helper everywhere.
3. **Deletion** removes tags and words for the source and nothing else. Reingest replaces
   by the same boundary.
4. **Candidates only.** Recall never becomes a claim. A recalled tag is evidence to be
   checked, not proof. Keep `answer_status` semantics unchanged.
5. **Ambiguity is a question, not a guess.** On `ambiguous`, ask the user; do not pick.
6. **Words stay explainable.** Every returned unit carries `shared`, `expanded`, `score`
   so a reviewer can see why it was recalled.

## 8. Open decisions (owner)

1. **Link rule.** Single shared non-hub word links tags (needed so fragments of a sense
   join) but also links senses through generic words ("lifted"). Options: require two
   independent links; add a part-of-speech filter (nouns carry sense, verbs less);
   weight links by idf; confirm with an embedding check; or accept explicit source facts
   as the strongest links.
2. **Unit size.** Sentence (current) vs paragraph vs window. Sentence is precise but
   sparse.
3. **Hub rule.** Ratio-based (current) vs learned per word from its sense split.
4. **Cross-source links.** Tags in different sources of one tenant can link. If sources
   must be strictly separate, compute links per scope.
5. **Decay and depth.** One carried hop at 0.5 today. More hops reach further and leak more.
6. **Embedding signal.** Use dense cosine between tags as a second link signal. This is the
   most likely fix for the crane merge and for sparse overlap.

## 9. Phases

1. (done) Prototype + tests + measured comparison, flag off.
2. Build a real evaluation set before touching the pipeline: real documents, questions
   written by someone who has not seen this code, ambiguous words, missing facts, and a
   dense-only baseline. Report wrong-answer rate and clarification rate separately.
3. Resolve open decision 1 and 6; make the crane xfail pass without losing the others.
4. (wired) On by default. Ingest, delete, and correction maintain the store. Retrieval
   adds at most eight sense-specific chunks and asks on an ambiguous word when a
   session id is present. Hub-only tags are not loaded, which keeps the crane senses
   apart at admission time. `recall_spread` itself is unchanged, so its crane xfails
   remain. `word_tags.json` stays until a real evaluation set says otherwise.
5. Scale: replace the O(T^2) component step with indexed word-to-tag traversal capped at
   a fixed budget, add indexes, and measure. The prototype is fine for thousands of tags,
   not millions.

## 10. Acceptance tests for the next agent

- All of `tests/test_resonance_groups.py` passes; the three strict xfails stay xfail until
  the corresponding fix lands, then flip to passing and drop the marker.
- `python tests/resonance_eval.py` precision for spreading does not drop below 0.88 and
  recall stays at or above 0.89 on this corpus.
- New: a scope test that a caller scoped to `a-p` gets identical recall results with and
  without `b-p` in the store.
- New: reingest and delete leave no tags, words, or counts for the source (DB-independent).
- New: with the flag off, every existing test result is unchanged.
