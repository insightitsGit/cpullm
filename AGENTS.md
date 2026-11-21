# CPU-LLM for AI agents

CPU-LLM (`pip install cpu-llm`) is a CPU-first evidence engine. It is **not** a generative language model. Use it as
a tool. It answers from ingested documents with exact citations, checks rules and arithmetic deterministically,
and proposes cited hypotheses that are clearly labelled unverified.

## Call it

- **Python:** create the appliance with `from cpu_llm.pipeline import Appliance` and
  `app = Appliance(namespace="...")` (use it as a context manager). Call `app.ingest(path_or_SourceDocument)`,
  then `app.ask(message, **options)`. On Windows, run it under `if __name__ == "__main__":`.
- **HTTP:** `cpu-llm-serve --secrets credentials.json`, then `POST /v1/ask` with
  `Authorization: Bearer <secret>` and a body of `{"message": "...", ...options}`.
- **Tool definitions:** [docs/agent-tool-schema.json](docs/agent-tool-schema.json).
- **Full contract:** [OpenAPI](docs/openapi.json).
- **Requires:** PostgreSQL with pgvector 0.7 or later (`VECTORPRISM_PG_DSN`), the `all-mpnet-base-v2` encoder cache,
  and about 3 GB of RAM.

## Choose the call

| Goal | Call |
|---|---|
| Exact quote of a named attribute, or a refusal | `ask("What is the <attribute> of <entity>?", strict_evidence=True)` |
| Grounded answer to another question | `ask(question)` |
| Cited report, article or email | `ask("Write a detailed report about <topic>")` |
| Rule proof | `ask("Infer whether <A> is bigger than <C>.")` or `ask(q, inference={"subject":..., "relation":..., "object":...})` |
| Arithmetic | `ask("Calculate 17 times 24")` |
| Untested connections across the whole knowledge base | `ask("Frontier: <topic>.", session_id=s)` |
| Check one hypothesis with evidence and a test plan | `ask("Deepen idea 3", session_id=s)`, `ask("Check this hypothesis: <A> may constrain <C> through <B>.")`, or `deepen=<entry>` |
| Literature synthesis on a topic | `ask("Research <topic>")` |
| Joins across knowledge bases | `ask("CrossDomain: <topic> using KBs: <a>, <b>")` |
| Inventory | `app.chunk_inventory("<source>")` or `POST /v1/chunks` |

## Branch on `answer_status`

- `answered`, `evidence_quote`, `derived_inference`: source-backed or derived. Use it and cite `answer_evidence`.
- `hypotheses`, `shortage`, `research_question`, `deepened`: unverified. Present as candidates with their
  citations and tests; never as facts.
- `insufficient_evidence`, `unsupported`: a correct refusal. Say the sources do not settle it.
- `conflicting`, `contradicted`: the sources disagree. Show both sides.
- `needs_clarification`: ask the user the question in `reply.text`, then reply with the same `session_id`.
- `partial`: a budget stopped the work. Check `incomplete` and `stop_reason`.
- `blocked`: refused by the guard or access policy. Do not retry.
- `conversation`, `external_unverified`: no source evidence.

## Rules

1. Never present an `UNVERIFIED_HYPOTHESIS` as fact. Frontier, Deepen, research and invention output is always
   unverified.
2. Keep citations (`answer_evidence`, `frontier.hypotheses[*].citations`, `deepen.links[*].support`).
3. In Frontier output, skip or flag entries whose `check.verdict` is `contested`. In Deepen, the informative
   statuses are `contested` and `missing`. A verdict of `incomplete` means the check stopped at a budget.
4. Send one specialist request per call. Combining `frontier`, `deepen`, `invent`, `nammade`, `cycle_search` or
   `inference` raises an error.
5. Use `session_id` for follow-ups and clarifications.
6. Strict mode (`strict_evidence=True` or header `X-CPU-LLM-Evidence-Mode: strict`) disables every hypothesis
   route.

More: [README](README.md) · [Consumer guide](docs/library-consumer-guide.md) · [Prompt-to-node map](docs/prompt-flag-map.md).
