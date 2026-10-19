# Test results, 2026-10-18

**Commit under test:** `18bbe51` on `main`.

**Command:**

```text
python -m pytest tests --tb=line -ra
```

**Result:** 180 passed, 0 failed, 17 errors, 2 warnings. Duration 546.09 s (9 minutes 6 seconds).

No assertion failed. The 17 errors are all in fixture setup. The test body never ran, so this run does not say whether those behaviors are correct.

## What was wrong

`Appliance()` opens PostgreSQL with the `vector` extension. When `VECTORPRISM_PG_DSN` is unset, `tests/test_pipeline.py` and `tests/test_upload.py` set it to:

```text
postgresql://vectorprism:vectorprism@localhost:5433/vectorprism
```

That is the DSN in the README. On this run nothing accepted the connection. psycopg raised `ConnectionTimeout` after both of these attempts:

* `localhost` port `5433` via `::1`
* `localhost` port `5433` via `127.0.0.1`

Docker Desktop was not running. The check was:

```text
docker ps -a --filter name=cpullm-pgvector
```

It failed with: the Docker API pipe `dockerDesktopLinuxEngine` was not found. The local container could not be started from this session.

## Tests that did not run

All sixteen tests in `tests/test_pipeline.py` share the module fixture `appliance`. The first one to build that fixture timed out, and pytest marked the rest of the module as the same setup error.

| Test | File |
| --- | --- |
| `test_allowed_question_resonates_the_vectorprism_chunk` | `tests/test_pipeline.py` |
| `test_stored_proposition_is_realized` | `tests/test_pipeline.py` |
| `test_supplied_homarus_proposition_is_realized` | `tests/test_pipeline.py` |
| `test_catalog_training_realizes_the_repeated_sentence` | `tests/test_pipeline.py` |
| `test_six_channel_nodes_quote_the_passages_and_suggest_discovery_for_a_why_question` | `tests/test_pipeline.py` |
| `test_numeric_facts_come_from_the_passage_and_the_causal_graph_comes_from_the_caller` | `tests/test_pipeline.py` |
| `test_empty_retrieval_realizes_the_design_abstention` | `tests/test_pipeline.py` |
| `test_ingest_saves_and_replaces_source_chunks` | `tests/test_pipeline.py` |
| `test_stated_measurement_keeps_claims_and_realizes_the_stored_sentences` | `tests/test_pipeline.py` |
| `test_wikitext_paragraph_is_retrieved_as_source_text` | `tests/test_pipeline.py` |
| `test_discovery_loop_is_opt_in` | `tests/test_pipeline.py` |
| `test_payment_turn_uses_the_corporate_policy` | `tests/test_pipeline.py` |
| `test_query_vector_is_encoded_once_and_reused` | `tests/test_pipeline.py` |
| `test_creative_writing_walks_the_article_and_leaves_the_answer` | `tests/test_pipeline.py` |
| `test_prompt_injection_stops_before_retrieval` | `tests/test_pipeline.py` |
| `test_a_named_article_is_the_answer_and_the_creative_walk` | `tests/test_pipeline.py` |
| `test_questions_about_an_uploaded_pdf_answer_from_that_file` | `tests/test_upload.py` |

`test_the_uploaded_pdf_keeps_every_sentence` does not open Postgres. It passed with the other 179 tests.

## How to fix

1. Start Docker Desktop and wait until `docker ps` returns.
2. Start the database on port 5433. If the container `cpullm-pgvector` already exists:

```text
docker start cpullm-pgvector
```

If it does not, create it with the image and account from the README:

```text
docker run -d --name cpullm-pgvector -p 5433:5432 -e POSTGRES_USER=vectorprism -e POSTGRES_PASSWORD=vectorprism -e POSTGRES_DB=vectorprism pgvector/pgvector:pg16
```

3. Confirm the port answers, then rerun only the tests that did not start:

```text
python -m pytest tests/test_pipeline.py tests/test_upload.py --tb=short
```

A timeout on the same DSN means the database is still down. An assertion failure after the fixture starts is a product bug and should be recorded as a new row in this file, with the assertion text and the fix. Do not treat today's 17 errors as product failures.

## Warnings

Three `DeprecationWarning` lines, all from generated extension types (`SwigPyPacked`, `SwigPyObject`, `swigvarlink`) while `tests/test_answering.py::test_a_paraphrase_uses_the_trained_extractor_when_it_is_present` imported its stack. They did not fail the test. No code change is required for them.

## What passed

The other 180 tests passed, including answering, fact bridge, frames, formats, the semantic format trigger, the capacity manager, documents, math, and the realizer checks. Those tests do not open `localhost:5433`.
