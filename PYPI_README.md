# CPU-LLM: Evidence-Based AI Engine

**A CPU-first, neuro-symbolic evidence engine: it answers from your documents with exact citations, checks rules and
calculations deterministically, and proposes cited, unverified research hypotheses.**

[![PyPI](https://img.shields.io/pypi/v/cpu-llm)](https://pypi.org/project/cpu-llm/)
[![Code license Apache 2.0](https://img.shields.io/badge/Code-Apache_2.0-green)](https://github.com/insightitsGit/cpullm/blob/main/LICENSE)
[![Python 3.11+](https://img.shields.io/badge/Python-3.11%2B-blue)](https://github.com/insightitsGit/cpullm/blob/main/pyproject.toml)

**Latest release:** [1.15.0](https://pypi.org/project/cpu-llm/1.15.0/), which adds the
[Frontier](#frontier-ranked-hypotheses-across-a-knowledge-base) and
[Deepen](#deepen-examine-one-hypothesis) hypothesis nodes. See the [changelog](https://github.com/insightitsGit/cpullm/blob/main/CHANGELOG.md).
Author **Amin Parva, Independent Engineer**. Code under Apache 2.0; free for individuals and teams.
[Enterprise enquiries](https://www.insightits.com/research-tools/cpu-llm).

## What it is, and what it is not

- **It is** an embeddable Python library and a local HTTP service. You ingest your documents (stored in
  PostgreSQL/pgvector), ask questions or give commands, and get back a structured result: an answer bound to exact
  source spans, a deterministic calculation, a refusal, or a labelled hypothesis.
- **It is not a large language model.** Despite the name, no billion-parameter model writes its answers. It uses
  small trained models for meaning and grammar (the `all-mpnet-base-v2` sentence encoder, an optional spaCy parser,
  trained projection heads) and symbolic code for retrieval, rules, arithmetic and checks. "CPU-LLM" refers to its
  CPU-first language pipeline.
- **Every output says what kind of claim it is.**
  - **Source-backed:** quoted spans with document IDs, offsets and chunk hashes.
  - **Derived:** a replayable rule proof or an exact calculation.
  - **Unverified:** hypotheses labelled `UNVERIFIED_HYPOTHESIS`, never promoted to facts or written back to the index.
  - **Refused:** `unsupported`, `insufficient_evidence`, or a clarification question.

## When to use it

| Use it for | Prefer something else for |
|---|---|
| Answers that must quote your sources exactly, or refuse (regulated, audited or on-premises work) | Fluent open-ended writing, chat or brainstorming without sources |
| Checking stated rules, intervals and arithmetic with an inspectable trace | Questions your documents do not cover |
| Cited reports and documents assembled from your sources | Creative prose (only bounded, source-checked wording is produced) |
| Literature synthesis: finding untested connections across many documents, then checking each one | Proving theorems or running experiments; hypotheses stay unverified |
| Running on ordinary CPUs, offline, with repeatable results | GPU-scale generation |

## Quickstart

Python 3.11 or later. About 3 GB of RAM for a running appliance.

**1. Install.**

```shell
python -m pip install "cpu-llm==1.15.0"
# Optional, recommended for Frontier and Deepen: a dependency parser.
python -m pip install "cpu-llm[prompt_nlp]==1.15.0"
python -m spacy download en_core_web_lg      # or en_core_web_sm
```

**2. Start PostgreSQL with pgvector 0.7 or later.** From a checkout, `docker compose up -d --wait postgres` starts
one on `127.0.0.1:5433` that matches the default connection string. Otherwise point `VECTORPRISM_PG_DSN` at your own
database. [Database setup](https://github.com/insightitsGit/cpullm/blob/main/docs/development-database.md).

**3. Allow the encoder download once.** The first appliance downloads `sentence-transformers/all-mpnet-base-v2`
from Hugging Face. To run offline, prepare the cache first: [encoder caching](https://github.com/insightitsGit/cpullm/blob/main/docs/offline-setup.md).

**4. Ingest and ask.** Save as a script; on Windows keep the `__main__` guard (the appliance starts worker
processes).

```python
from cpu_llm.pipeline import Appliance
from cpu_llm.documents import SourceDocument

def main():
    with Appliance(namespace="quickstart") as app:
        app.ingest(SourceDocument("helios-manual", (
            "Helios is a backup service.",
            "The retention period of Helios is 30 days.",
            "Helios stores encrypted backups.",
        )))
        # Strict: an exact quote or a refusal.
        strict = app.ask("What is the retention period of Helios?", strict_evidence=True)
        print(strict["answer_status"])       # evidence_quote
        print(strict["answer_evidence"])     # [{'document_id': 'helios-manual-p0002', ...}]
        # Ordinary: a grounded answer with its citation.
        ordinary = app.ask("What does Helios store?")
        print(ordinary["answer_status"])     # answered
        print(ordinary["reply"]["text"])     # Helios stores encrypted backups.

if __name__ == "__main__":
    main()
```

Strict mode answers explicit named-attribute questions ("What is the *attribute* of *entity*?") and refuses
everything else with `unsupported`. Ordinary mode answers a wider range of questions and still cites its sources.

`app.ingest` also accepts a file or folder path (`.txt`, `.md`, `.html`, `.pdf`, `.docx`, `.csv`, `.xlsx`, `.xlsm`,
`.epub`) and splits it into paragraph chunks with IDs such as `helios-manual-p0001`.

**5. Read the result.** Branch on `answer_status`; see [Reading a result](#reading-a-result).

To serve the same API over HTTP, see [HTTP service](#http-service). For agents, see
[Using CPU-LLM from an AI agent](#using-cpu-llm-from-an-ai-agent).

## Capability map

Every capability goes through `app.ask(message, **options)`, or `POST /v1/ask` with the same options in the JSON
body. Most can be triggered by the prompt itself or by an explicit option.

| Task | Prompt form | Python / HTTP option | Read | Kind of claim |
|---|---|---|---|---|
| Answer only with exact quotes, or refuse | "What is the *attribute* of *entity*?" | `strict_evidence=True` | `reply.text`, `answer_evidence` | source-backed |
| Ordinary grounded answer | any question | (default) | `answer_status`, `judgment`, `answer_evidence` | source-backed |
| Cited article, report, email or memo | "Write a detailed report about X" | — | `document`, `research_plan` | source-backed composition |
| Wider search | "Search deeply for X" | `deep=True` | `reply.text` | source-backed |
| Rule proof (transitivity, membership, parts, requirements) | "Infer whether A is bigger than C" | `inference={...}` | `inference` (proof) | derived |
| Dated intervals, proportions, explanation comparison | "Temporal: sources: a-p0000, b-p0001" | `inference={"mode": ...}` | `inference` | derived / unverified |
| Arithmetic | "Calculate 17 times 24" | `math=True` | `math_result` | derived |
| Covenant and refund checks | "Decide this LedgerCovenant test …" | `finance=True` | `finance_result` | derived |
| Interval check across knowledge bases | "Constraint Check: X using KBs: a, b" | — | `invention` (`node: constraint_check`) | derived |
| Join premises across knowledge bases | "CrossDomain: X using KBs: a, b" | — | `invention` (`node: crossdomin`) | unverified |
| Research: invention, source hypotheses, comparison | "Research X", "Investigate X" | — | `research_options`, `research_workspace` | unverified |
| Concept invention | "Invention: X", "Create a new concept from X" | `invent=True` | `invention.proposals` | unverified |
| Passage comparison scan | "Nammade: X" | `nammade=True` | `nammade.evaluations` | diagnostic |
| Relationship loops | "Show relationship loops for X" | `cycle_search={"seed": "X"}` | `cycle_exploration` | source-backed paths |
| Ranked hypotheses across the whole knowledge base | "Frontier: X", "What unexplored connections exist around X?" | `frontier=True` or `{...}` | `frontier.hypotheses` | unverified, checked |
| Check one hypothesis link by link, with a test plan | "Deepen: …", "Check this hypothesis: …", "Deepen idea 3" | `deepen=<hypothesis>` | `deepen` | unverified, checked |
| Count, list or delete chunks | "List chunks for notes.pdf" | `app.chunk_inventory()`, `app.delete_chunk()` | `chunk_inventory` | — |
| Simpler wording | "… Use simple English." | `target_level="A2"` with `Appliance(prismlexicon=True)` | `reply.text` | same as the answer |

Natural wording routes to the specialist nodes only when the prompt clearly asks for them. Ordinary questions keep
the normal answer path. The full trigger list is the [prompt-to-node map](https://github.com/insightitsGit/cpullm/blob/main/docs/prompt-flag-map.md), and a
machine-readable copy is [prompt-flag-map.json](https://github.com/insightitsGit/cpullm/blob/main/docs/prompt-flag-map.json).

## Reading a result

`ask` returns a dictionary. These fields are present on almost every result:

| Field | Meaning |
|---|---|
| `answer_status` | What kind of result this is (table below). Branch on this first. |
| `reply.text` | The text to show. It carries the labels and notes the result needs. |
| `answer_evidence` | The source spans behind the reply: `document_id`, quote, offsets, `chunk_sha256` |
| `judgment` | The delivery judgment: `outcome`, verification scope, accepted and rejected spans |
| `routing` | `executed_nodes` (graph stages that ran) and `post_stages` (routes outside the graph) |
| node receipt | `frontier`, `deepen`, `inference`, `invention` (also CrossDomain and Constraint Check), `nammade`, `document`, `cycle_exploration`, `math_result`, `finance_result`: the full structured output of the node that answered |

| `answer_status` | What it means | What to do |
|---|---|---|
| `answered` | An ordinary answer whose claims passed the grounding checks | Use it; cite `answer_evidence` |
| `evidence_quote` | The reply is the exact supporting passage(s) | Use the quote as the answer |
| `derived_inference` | A rule proof over cited records | Use it; the proof is in `inference.proof` |
| `deepened` | Deepen finished its link-by-link check | Read `deepen.verdict` and `deepen.links` |
| `hypotheses` | Unverified hypotheses with citations and tests | Present them as candidates to examine, never as facts |
| `shortage` | Frontier found fewer than 10 hypotheses; the list is not padded | As above; expect fewer |
| `research_question` | Relevant sources but no testable proposal; a research question is returned | Present it as a question |
| `nammade` | A passage-comparison scan | Diagnostic only |
| `insufficient_evidence` | The sources do not settle it | Say so; ingest more material if appropriate |
| `unsupported` | Outside what the route can answer (for example strict mode on an open question) | Rephrase as an explicit question, or use another route |
| `conflicting`, `contradicted` | The sources disagree, or explicitly contradict the requested relation | Show both sides; do not pick one |
| `needs_clarification` | The request is ambiguous; `reply.text` is the question to ask | Ask the user, then repeat with the same `session_id` |
| `partial` | A budget or snapshot limit stopped the work; results may be incomplete | Use with care; check `incomplete` and `stop_reason` |
| `blocked` | The guard or access policy refused the request | Do not retry the same request |
| `conversation` | A built-in social reply ("Who are you?") | No evidence involved |
| `external_unverified` | The optional external-LLM fallback answered (off by default) | Treat as unverified |

There is no single "verified" flag. For a production integration, read the layers in order: transport errors,
delivery holds, the producing node, then evidence. The [consumer guide](https://github.com/insightitsGit/cpullm/blob/main/docs/library-consumer-guide.md#result-routing-for-an-agent)
gives a helper that collects them.

## Using CPU-LLM from an AI agent

CPU-LLM works well as a tool behind an agent. The agent handles conversation and judgment; CPU-LLM supplies
evidence, checks and candidate hypotheses that the agent can cite.

**Rules for an agent**

1. **Use `strict_evidence=True` for named-attribute lookups** ("What is the dosage of X?"). You get an exact quote
   or a refusal, never paraphrase. For other questions use ordinary mode, which still cites its sources.
2. **Never state an `UNVERIFIED_HYPOTHESIS` as a fact.** Present `hypotheses`, `research_question`, invention and
   Frontier output as candidates, with their citations and falsification tests.
3. **Keep the citations.** Pass `answer_evidence` (or the node's citations) through to the user. They are the value.
4. **On `needs_clarification`, ask the user.** Send the answer back with the same `session_id`.
5. **Use `session_id` for follow-ups.** It powers "Deepen idea 3", "Explain proposal 1" and clarification turns.
6. **Respect refusals.** `insufficient_evidence`, `unsupported` and `blocked` are correct answers, not errors to
   work around.
7. **Submit one specialist request per call.** Combining, for example, `frontier` and `invent` raises an error.

**Recommended workflows**

- **Answer a question:** for a named attribute, `ask(question, strict_evidence=True)`. Otherwise, or when strict
  returns `unsupported`, call `ask(question)` and read `answer_status`, `answer_evidence` and `judgment`.
- **Write a cited document:** `ask("Write a detailed report about X")`, then read `document` and `research_plan`.
- **Explore an open question:**
  1. `ask("Frontier: X", session_id=s)` returns up to 50 ranked hypotheses; the first five are already checked.
  2. Skip entries flagged `contested`.
  3. `ask("Deepen idea 3", session_id=s)` gives that entry's evidence per link, confounders and a test plan.
- **Check a claim someone made:** `ask("Check this hypothesis: A may constrain C through B.")`.
- **Verify a rule-based conclusion:** `ask("Infer whether the Kestrel requires a radio.")`, then read
  `inference.proof`.

**Tool definitions.** [`docs/agent-tool-schema.json`](https://github.com/insightitsGit/cpullm/blob/main/docs/agent-tool-schema.json) defines `cpu_llm_ask`,
`cpu_llm_ingest` and `cpu_llm_list_chunks` as function-calling tools, mapped to the Python API and the HTTP
routes. [`AGENTS.md`](https://github.com/insightitsGit/cpullm/blob/main/AGENTS.md) is a one-page brief that agent frameworks can load directly. The HTTP contract is
[OpenAPI 3.1](https://github.com/insightitsGit/cpullm/blob/main/docs/openapi.json).

## Feature guides

### Strict evidence: quote or abstain

`strict_evidence=True`, the `X-CPU-LLM-Evidence-Mode: strict` header, a `[strict-evidence]` prompt marker, or an
operator floor (`Appliance(strict_evidence=True)`, `cpu-llm-serve --strict-evidence`) turns on strict mode. Strict
answers are exact source spans, recognized exact calculations, or `unsupported`. Learned producers, tone rewriting,
invention, research, Frontier and Deepen are all off. Ingest one factual statement per record for the recognized
grammar.

```text
What is the strength of Fictional Luma?        -> evidence_quote: The strength of Fictional Luma is 0.75 mg.
Which antibiotic should Case Birch receive?    -> unsupported
```

These are fictional label fixtures, not a clinical system. [Recorded healthcare demo](https://github.com/insightitsGit/cpullm/blob/main/examples/healthcare/sample-run/README.md)
· [Strict grammar and limits](https://github.com/insightitsGit/cpullm/blob/main/docs/strict-evidence-spec.md).

### Ordinary answers and retrieval

The ordinary pipeline runs 27 graph stages. Retrieval combines six signals over PostgreSQL/pgvector: dense,
relational, disentangled, hyperbolic, identity and causal. Only the dense and identity projection heads are trained
and bundled; the others use their implemented signals or symbolic paths.

Before grounding, the request planner:
- splits compound questions;
- repairs conservative typos;
- separates presentation instructions ("as a table") from the facts requested;
- normalizes conversational wording ("Can you tell me what …").

A similarity score is never treated as proof. [Architecture](https://github.com/insightitsGit/cpullm/blob/main/docs/current-design.md) ·
[Prompt ingestion](https://github.com/insightitsGit/cpullm/blob/main/docs/prompt-ingestion.md) · [Answer contract](https://github.com/insightitsGit/cpullm/blob/main/docs/library-consumer-guide.md#complete-ask-contract).

### Cited documents and tone

"Write a detailed article about Helios", "Draft a concise email to Alex about Helios" or "Write a report about
Helios in 60 items" build an inspectable `research_plan`. They then select evidence from one authorized snapshot and
compose sections whose sentences are checked against source predicates. Numbers, negation and qualifiers are
kept. Evidence shortage is reported, never padded. Appending "in a friendly tone" adds a verified tone stage. Strict
documents keep plain quotations.

```text
Helios stores encrypted backups and uses PostgreSQL for metadata.
```

[Document and tone manual](https://github.com/insightitsGit/cpullm/blob/main/docs/document-generation-user-guide.md) · [Tone specification](https://github.com/insightitsGit/cpullm/blob/main/docs/stylistic-generation-spec.md).

### Inference: proofs, calculations and structured analyses

- **Deduction.**
  - "Infer whether the elephant is bigger than the cat" (after ingesting "The elephant is bigger than the donkey"
    and "The donkey is bigger than the cat") returns `derived_inference` with a replayable proof.
  - The rule families cover ordering, taxonomy, physical parts and location, possession, and class requirements:
    `bigger_than`, `has`, `member_of`, `subclass_of`, `physical_part_of`, `physically_contains`, `located_in`,
    `requires`.
  - In the automatic research checks, other relationships record `no_applicable_rule`. Compound names and trailing
    clauses are rejected rather than turned into predicates.
- **Research checks.** Research, invention, Nammade and CrossDomain check the applicable rules automatically
  (`research_inference.receipts`). This never promotes their hypotheses.
- **Structured analyses** over explicitly selected JSON records:
  - `temporal` (date intervals);
  - `inductive` (a Bernoulli proportion with a 95% Wilson interval);
  - `abductive` (declared explanations compared by coverage).

  Call them with, for example, `ask("Compare the two intervals.", inference={"mode": "temporal", "source_ids": [...]})`.

Strict mode refuses derived answers. [Inference guide](https://github.com/insightitsGit/cpullm/blob/main/inference-guide.md) · [Design](https://github.com/insightitsGit/cpullm/blob/main/docs/inference-node-design.md).

### Research, invention and comparison

"Research X", "Investigate X" and "Propose a testable hypothesis about X" run three methods in parallel on one
authorized snapshot:
- **Innovation:** cross-chunk proposals;
- **Hypothesis generation:** source predictions with proposed tests;
- **Nammade:** passage comparison.

The **abductive bridge** then emits a schema-bound hypothesis only when two quoted bounds on one observable conflict
and differ on a regime variable named in the passages. Everything stays `UNVERIFIED_HYPOTHESIS` with
`promotion: blocked`.

"Invention: X" proposes cited cross-chunk connections. Follow it with "Explain proposal 1" and "Go deeper" in the
same session.

Worked examples:
- dark matter: a velocity-dependent cross-section test linking dwarf-galaxy cores to the Bullet Cluster bound;
- the Fernhouse invention fixture;
- leptogenesis, from a cited hypothesis to a numerical scan with `app.scan_leptogenesis`.

[Research and cycles guide](https://github.com/insightitsGit/cpullm/blob/main/docs/research-cycle-user-guide.md) · [Invention and CrossDomain](https://github.com/insightitsGit/cpullm/blob/main/docs/taxonomy-invention-spec.md) ·
[Abductive bridge](https://github.com/insightitsGit/cpullm/blob/main/docs/abductive-bridge-node.md) · [Nammade](https://github.com/insightitsGit/cpullm/blob/main/docs/nammade-channel-equilibrium-node.md) ·
[Constraint evaluator](https://github.com/insightitsGit/cpullm/blob/main/docs/invention-constraint-evaluator-spec.md) · [Evidence research workspace](https://github.com/insightitsGit/cpullm/blob/main/docs/evidence-research-spec.md).

### Several knowledge bases: CrossDomain and Constraint Check

Name sources with a knowledge-base prefix (`physics-seesaw.md`, `math-rotations.md`) and select two to seven
prefixes. "CrossDomain: Casas-Ibarra using KBs: physics, math" joins one cited premise from each and checks a shared
relation. "Constraint Check: Leptogenesis using KBs: physics, math, experiment" compares a prediction with a bound,
or two measured intervals, after unit conversion. A missing premise is reported as a gap.
[CrossDomain spec](https://github.com/insightitsGit/cpullm/blob/main/docs/cross-domain-research-spec.md).

### Relationship loops

"Show relationship loops for Alpha", or `cycle_search={"seed": "Alpha", "limits": {"max_rounds": 1000}}`, finds
closed source-backed paths. For example: "Alpha causes Beta; Beta causes Gamma; Gamma causes Alpha". It never infers
the shortcut. Default 1,000 rounds, ceiling 100,000. [Cycle guide](https://github.com/insightitsGit/cpullm/blob/main/docs/research-cycle-user-guide.md).

### Frontier: ranked hypotheses across a knowledge base

Added in 1.15.0. Frontier proposes possibilities that no single source states. It collects the relations your
sources state ("A limits B", "B drives C", "X undermines Y") and tries every combination around a topic, within
budgets. A candidate is kept only if it passes three checks:

1. **Abductive:** the relations combine into a coherent explanation.
2. **Deductive:** every premise is an exact source span, no source negates a premise or the conclusion, and the rule
   engine does not contradict it.
3. **Pre-thinker:** the candidate is not malformed, circular, drawn from one source, or a restatement of one
   sentence.

```python
reply = app.ask("Frontier: grokking.")                          # or "What unexplored connections exist around grokking?"
receipt = reply["frontier"]
receipt["status"]                                               # hypotheses, shortage, insufficient_evidence, partial
for item in receipt["hypotheses"]:
    item["text"], item["scores"], item["citations"], item["falsification_test"], item.get("check")
reply = app.ask("grokking", frontier={"deepen_top": 3, "limits": {"max_seconds": 60}})
```

- **Output.**
  - 10 to 50 entries (hard cap 50). Fewer gives `shortage`; the list is never padded.
  - Each entry has `source_support`, `deductive_relevance` and `novelty` scores (0–1), citations with exact quotes,
    assumptions and a falsification test.
  - Ranking is by support, then relevance, then novelty. Relevance is lowered for terms found almost everywhere, and
    no single term may fill the top of the list.
- **Automatic check.** The first five entries are checked with Deepen and marked with their verdict. A contested
  entry is flagged with the contradicting quote. Set `deepen_top` (0–10) to change how many.
- **Budgets.**
  - Rounds, candidates, edges, memory and time, with defaults of 1,000 rounds of 256 candidates, 200,000
    candidates and 60 s.
  - A stopped run sets `incomplete: true`.
  - The first prompt on a knowledge base parses it (tens of seconds for about 1,000 chunks); later prompts take
    seconds.
- **Parser.** With the `prompt_nlp` extra and an English spaCy model, relations come from a dependency parse;
  otherwise a regex reader is used. `FRONTIER_PARSER` names a model or forces `regex`.

On evaluation corpora of 64–153 arXiv papers, a minority of entries were strong research leads and many were weak.
Treat the list as candidates to screen. [Design](https://github.com/insightitsGit/cpullm/blob/main/docs/frontier-node-design.md) ·
[Evaluation](https://github.com/insightitsGit/cpullm/blob/main/docs/reviews/2026-11-21-frontier-v3/report.md).

### Deepen: examine one hypothesis

Added in 1.15.0. Deepen takes one hypothesis and checks it link by link against the same sources. Pass a Frontier
entry, write "Deepen: A may constrain C through B.", or say "Deepen idea 3" after a Frontier answer in the same
session.

```python
receipt = app.ask("Deepen this.", deepen=frontier_entry)["deepen"]
receipt["verdict"]          # all_links_supported, partly_supported, contested, unsupported
receipt["links"]            # each: source, target, status, support, counter
receipt["predictions"], receipt["setups"], receipt["confounders"]
receipt["test_plan"]        # design, manipulate, measure, mediator, controls, steps, fails_if
```

Each link is `supported`, `contested`, `counter_only`, `weak` or `missing`; a source stating the opposite direction
or negating the link counts against it. For Frontier's own entries, "supported" is nearly guaranteed, because each
entry is built from source sentences. The informative signals are `contested` and `missing`. In one evaluation run,
Frontier proposed that low weight decay increases generalization through the grokking phase; Deepen marked it
contested, because the cited paper also states that *increasing* weight decay leads to that phase.
[Deepen node](https://github.com/insightitsGit/cpullm/blob/main/docs/deepen-node.md).

### Deterministic finance

`LedgerCovenant` evaluates supplied covenant fields and `RefundProof` reviews supplied sales-tax findings, with
explicit precision and rounding. The direct validator needs no database:

```python
from cpu_llm.finance import validate_message
result = validate_message("""Decide this LedgerCovenant test.
comparator: lte
threshold: 4.50
numerator: compliance_certificate 9000001
denominator: compliance_certificate 2000000
ratio places: 6
""")
print(result["text"])     # 4.5000005 -> six-place half-up 4.500001 > 4.500000: BREACH
```

Supplied fields are not authenticated records, and a breach result is not a legal finding.

### Simpler wording (PrismLexicon)

Off by default. `Appliance(prismlexicon=True)` plus `target_level="A2"`, or "Use simple English." after a question,
simplifies a small set of context-checked expressions. Quotations and evidence are unchanged.
[PrismLexicon](https://github.com/insightitsGit/cpullm/blob/main/docs/prismlexicon.md).

### Chunk management and large documents

- **Inventory:** "How many chunks do we have?" or "List chunks for notes.pdf"; also `app.chunk_inventory(...)` and
  `POST /v1/chunks`.
- **Deleting one chunk:** "Delete chunk notes-p0001" or `app.delete_chunk(...)` returns a preview and a
  confirmation token (five minutes, tied to the caller and row revision). Team callers need the `admin` role.
- **Large files:** `app.ingest("book.pdf", encoder_workers=4)` tries parallel encoding (one to four workers). A
  162-page PDF took 85.7 s with one worker.

[Chunk management](https://github.com/insightitsGit/cpullm/blob/main/docs/chunk-management-spec.md) · [Ingestion performance](https://github.com/insightitsGit/cpullm/blob/main/docs/ingestion-performance-spec.md).

### Optional external LLM fallback

Off by default. A configured provider adapter can answer eligible unsupported standalone requests. Those replies
are labelled `external_unverified`; strict mode bypasses it.
[Configuration](https://github.com/insightitsGit/cpullm/blob/main/docs/library-consumer-guide.md#optional-external-llm-fallback).

## HTTP service

```shell
cpu-llm-serve --secrets credentials.json --host 127.0.0.1 --port 8765
```

```shell
curl -s http://127.0.0.1:8765/v1/ask -H "Authorization: Bearer $CPU_LLM_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"message": "Frontier: grokking.", "session_id": "s1"}'
```

- **Routes** (all POST): `/v1/ask`, `/v1/ingest`, `/v1/correct`, `/v1/delete`, `/v1/chunks`, `/v1/delete-chunk`.
- **Credentials:** the file stores SHA-256 digests only, each with a tenant and the allowed source prefixes.
  Plaintext secrets are refused.
- **Strict mode** is available per request (`"strict_evidence": true` or the header) or for the whole service
  (`--strict-evidence`).
- **Capacity:** the service handles one request at a time, has no built-in TLS, and binds to loopback by default.
  Put it behind your own gateway.

[OpenAPI 3.1 contract](https://github.com/insightitsGit/cpullm/blob/main/docs/openapi.json) · [HTTP and credentials](https://github.com/insightitsGit/cpullm/blob/main/docs/library-consumer-guide.md#authenticated-http-service) ·
[Enterprise pilot runbook](https://github.com/insightitsGit/cpullm/blob/main/docs/enterprise-pilot-runbook.md).

## Requirements and limits

- **Runtime:**
  - Python 3.11 or later;
  - PostgreSQL with pgvector 0.7 or later (older versions lack `subvector`);
  - about 3 GB of RAM per appliance;
  - the `all-mpnet-base-v2` encoder cache (a one-time download, or prepared offline).
- **Optional:**
  - the `prompt_nlp` extra and a spaCy English model, for better Frontier and Deepen extraction and prompt parsing;
  - the `coreference` and `fastcoreference` extras, for reference resolution.
- **Windows:** construct and call the appliance under `if __name__ == "__main__":`.
- **Language:** English, with bounded grammars. Topic matching is lexical, and aliases, joins and conflict detection
  are incomplete.
- **Evidence:** hashes prove consistency with stored text, not that a source is true. A strict quote can preserve an
  incorrect source. "Zero hallucination" is a property of the strict contract, not a general accuracy guarantee.
- **Hypotheses:** no node fits curves, runs simulations or changes a hypothesis into a verified result.

## Verification

The repository suite for 1.15.0 reports **1,287 passed, 56 skipped, 3 xfailed and 3 failed**. The three failures
predate this release (`test_cycle_composition` ×2 and `test_request_pipeline_benchmark`). The run used a disposable
PostgreSQL 16 with pgvector 0.8. The installed wheel was checked in a clean environment.
[1.15.0 build validation](https://github.com/insightitsGit/cpullm/blob/main/docs/releases/1.15.0-build-validation.md) · [Testing results](https://github.com/insightitsGit/cpullm/blob/main/docs/testing-results.md).

Demos (after database and encoder setup):

```shell
cpu-llm-demo healthcare --out healthcare-demo-output
cpu-llm-demo conversation --out conversation-demo-output
```

These are component and integration checks on authored fixtures, not an independent accuracy benchmark.

## Enterprise and commercial evaluation

The Apache 2.0 package is free for self-managed use by organizations of any size. For paid pilots, implementation
or support, contact **Amin Parva** through Insight IT Solutions:
[CPU-LLM enquiries](https://www.insightits.com/research-tools/cpu-llm).

Pilot scopes include private-credit covenant monitoring, on-premises and sovereign deployments, and regulatory
workflow adapters. These are integration opportunities, not claims of deployed results or automatic compliance.

## Documentation map

- **Start here:**
  - [Consumer guide](https://github.com/insightitsGit/cpullm/blob/main/docs/library-consumer-guide.md): the full ask contract, result routing, HTTP;
  - [Prompt-to-node map](https://github.com/insightitsGit/cpullm/blob/main/docs/prompt-flag-map.md);
  - [Changelog](https://github.com/insightitsGit/cpullm/blob/main/CHANGELOG.md).
- **Answers and documents:**
  - [Strict evidence](https://github.com/insightitsGit/cpullm/blob/main/docs/strict-evidence-spec.md);
  - [Document manual](https://github.com/insightitsGit/cpullm/blob/main/docs/document-generation-user-guide.md);
  - [Architecture](https://github.com/insightitsGit/cpullm/blob/main/docs/current-design.md).
- **Reasoning:**
  - [Inference guide](https://github.com/insightitsGit/cpullm/blob/main/inference-guide.md);
  - [Research and cycles](https://github.com/insightitsGit/cpullm/blob/main/docs/research-cycle-user-guide.md);
  - [Invention and CrossDomain](https://github.com/insightitsGit/cpullm/blob/main/docs/taxonomy-invention-spec.md);
  - [Abductive bridge](https://github.com/insightitsGit/cpullm/blob/main/docs/abductive-bridge-node.md).
- **Hypothesis nodes:**
  - [Frontier design](https://github.com/insightitsGit/cpullm/blob/main/docs/frontier-node-design.md);
  - [Deepen node](https://github.com/insightitsGit/cpullm/blob/main/docs/deepen-node.md);
  - [Evaluations](https://github.com/insightitsGit/cpullm/blob/main/docs/reviews/2026-11-21-frontier-v3/report.md).
- **Operations:**
  - [Database](https://github.com/insightitsGit/cpullm/blob/main/docs/development-database.md);
  - [Offline encoder](https://github.com/insightitsGit/cpullm/blob/main/docs/offline-setup.md);
  - [Enterprise runbook](https://github.com/insightitsGit/cpullm/blob/main/docs/enterprise-pilot-runbook.md);
  - [Release provenance](https://github.com/insightitsGit/cpullm/blob/main/docs/release-publishing.md).
- **Background:**
  - [Whitepaper](https://www.insightits.com/research-tools/cpu-llm/whitepaper);
  - [Nammade Continuum, Verified Edition](https://github.com/insightitsGit/cpullm/blob/main/docs/nammade-continuum-verified-edition.md), the author's companion article
    (saving it did not run a physics audit).

## License and citation

Code: [Apache-2.0](https://github.com/insightitsGit/cpullm/blob/main/LICENSE). Bundled WikiText-2 data is under **CC BY-SA 3.0/GFDL** with separate attribution;
see [third-party notices](https://github.com/insightitsGit/cpullm/blob/main/THIRD_PARTY_NOTICES.md). The Apache label does not cover the bundled data.

Cite as **cpu-llm: Evidence-Based AI Engine**, Amin Parva, the repository URL, and the exact version or commit
evaluated.
