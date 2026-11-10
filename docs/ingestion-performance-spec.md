# Large document ingestion

The catalog path encodes each chunk once in batches of 32. The index writes the original VectorPrism tensor, and graph and taxonomy processing reuse it. PostgreSQL deletion and insertion for source replacement share one transaction. If encoding or writing fails, PostgreSQL rolls back the replacement. Graph and taxonomy updates run after the vector transaction.

## Bounded pipeline design

Preserve existing chunk boundaries, source IDs, source spans, and ordering. A streaming parser should buffer page or section fragments until it can emit a complete chunk. A bounded queue should feed encoder batches to one ordered database writer. Close workers and roll back a failed replacement before returning an error. Coordinate replacement and concurrent reads at the source level. Graph and taxonomy stores require their own recovery or rebuild strategy because the PostgreSQL transaction cannot roll them back.

Keep one encoder worker as the default until measurements establish a gain from more. Compare one, two, and four workers with the same CPU thread budget and record parsing, encoding, writes, graph processing, elapsed time, and peak memory. Measure database and graph parity and retry behavior as well as throughput. Asynchronous request handling is a separate change from CPU parallelism.

## Initial measurement

A 256-chunk synthetic document was ingested twice per path in fresh namespaces with disposable PostgreSQL. The comparison reproduced the old double-encoding path and excluded appliance startup. Mean elapsed time fell from 4.60 seconds to 2.48 seconds. Encoder input fell from 512 to 256 chunks per run. These timings measure ingestion of already split text. PDF parsing and peak memory were outside this measurement.

## Encoder concurrency probe

The cached CPU encoder processed 384 synthetic chunks in batches of 32. With a nominal budget of four Torch compute threads, median encode-only times over two runs were 3.81 seconds with one worker and four threads, 3.46 seconds with two workers and two threads each, and 2.98 seconds with four workers and one thread each. Outputs matched the reference within relative tolerance 1e-5 and absolute tolerance 1e-6 in all six runs.

The probe shared a warmed encoder and excluded PDF parsing, database writes, graph updates, and peak memory. It does not establish an end-to-end ingestion speedup.

## Opt-in parallel encoding

Use `app.ingest("book.pdf", encoder_workers=4)` to encode batches in parallel.
The default is one worker. The maximum is four. The executor processes a
bounded window of 32 chunks per worker and one caller thread writes tensors
in input order. Parsing still loads the document before encoding. If an encoder
worker fails, PostgreSQL rolls back the replacement before the error returns.
Thread-pool sizing does not change the application's Torch thread settings.

### Whole-PDF verification

The [MIT 18.04 Complex Analysis notes](https://math.mit.edu/~dunkel/Teach/18.04_2019S/notes/1804_Main.pdf)
produced 265 chunks from 162 pages. On one Windows host with disposable
pgvector, one worker with four Torch threads took 85.71 seconds and peaked at
3.00 GiB of process working set. Four workers with one Torch thread each took
113.68 seconds and peaked at 6.53 GiB. Both runs stored identical chunk IDs,
text, and dense vectors and returned the same five retrieval IDs for a Cauchy
integral formula query. This comparison used one run per configuration. The
one-worker default remains appropriate for this workload.
