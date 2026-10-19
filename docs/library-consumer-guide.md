# Library consumer guide for agents

This guide describes the repository API reviewed through `9d6fbe8` on 2026-10-19. Package metadata remains 1.8.0, but this revision includes changes after the `v1.8.0` release tag. Pin the evaluated source commit when integrating, inspect signatures, and run applicable tests when updating. Version metadata alone does not establish which implementation a published wheel contains.

Read [README](../README.md) for installation and capability limits. This document supplies the integration contract, not a certificate of general correctness.

## Constructing and closing an appliance

```python
from cpu_llm.pipeline import Appliance

with Appliance(namespace="tenant_alpha") as app:
    # Ingest data before asking this tenant questions.
    pass
```

Constructor arguments are `checkpoint: Path | None`, and keyword-only `dsn`, `child_safety`, `namespace`, `on_escalate`. `dsn=None` uses `VECTORPRISM_PG_DSN` and then the development DSN in `retrieval.py`. Constructing an appliance loads the encoder/retrieval stack, connects to PostgreSQL, creates local state, and starts a reusable Thinker pool. It is not a lightweight pure-function wrapper.

When running a Python script on Windows, put appliance construction and calls inside a function invoked under `if __name__ == "__main__":`; the worker pool uses child processes. The README contains a complete guarded example. The short snippets in this guide describe operations to perform inside that application entry point.

Use `with` or `close()` for worker cleanup. Keep one stable working directory for a deployment: local graph, word tags/relations, resonance assets, and format cache live beneath `.chorusgraph/cpu-llm/`, with a subdirectory for named namespaces. These files are separate from PostgreSQL. Reusing the same working directory/namespace for a different DSN does not automatically isolate the local cache.

Namespaces are normalized to lowercase; runs of characters outside `[a-z0-9_]` become `_`, surrounding underscores are stripped, and the result is capped at 48 characters. Different raw names can normalize to the same tenant. Provision and store canonical tenant IDs rather than accepting arbitrary names as independent identities. The default tenant is `cpu-llm`; named tenants use `ns_<slug>` schemas and their own vector tables.

## Complete ask contract

Current signature, with annotations simplified for readability:

```python
def ask(
    message,
    propositions=None,
    *,
    discover=False,
    imagine=False,
    deep=False,
    math=False,
    finance=False,
    payment=None,
    authority=None,
    objective=None,
    hypothesis=None,
    causal_graph=None,
    realization="deterministic",
    account=False,
    grade=None,
    child_safety=None,
    session_id=None,
    caller=None,
    as_of=None,
): ...
```

- `message`: English question/request text. Automatic typo correction can change it using the tenant's stored vocabulary. Inspect `typos` and, when present, `original_message` before interpreting a decision.
- `propositions`: an optional list of `cpu_llm.ir.schema.EIRProposition` objects for cognition. This is an advanced override; the pipeline also requires compatible retrieved tensor/proposition pairing. It is not a list of plain strings and is not an unrestricted fact-injection interface.
- `discover`: enable the discovery loop; merely asking why does not enable it. This is an optional evidence-gathering path, not permission to invent missing parameters.
- `imagine`, `deep`, `math`, `finance`: force their respective optional agents. Other behavior is classified from the request. There are no public `summarize=`, `sources=`, or `format=` kwargs; ask for those in the message.
- `payment`, `authority`: supply both or neither. Mismatched presence raises `ValueError`. These are the proposal/authority objects consumed by PrismAgenticPay; this is separate from local `finance_result` checks and is not a payment execution API.
- `objective`, `hypothesis`, `causal_graph`: caller-owned PrismThinker context objects. The pipeline does not supply a missing target or causal graph merely because a passage has a number or says because. A caller causal graph is a supplied assertion, not a graph independently proved from text.
- `realization`: `"deterministic"`, `"evidence_neural"`, or `"model01"`; other values raise `ValueError`. Model01 already runs as a graph node on the ordinary path, so `"model01"` does not select a separately trained model. `"evidence_neural"` invokes an additional N0 realization result with deterministic fallback because no trained construction-ranker checkpoint is shipped. It does not force every reply producer through a new neural verifier.
- `account`: opt into the N0 full-account planning/rendering path. It can affect displayed text when no other optional agent takes precedence. It is not a general multi-record reasoning switch or a universal provenance report.
- `grade`, `child_safety`, `session_id`: accepted but discarded by `ask` in this checkout. Normal results explicitly report child safety off. Do not assume that constructor gate objects, a session string, or these keywords enforce a safety policy or isolate conversation state.
- `caller`: a `CallerContext` whose `tenant_id` must equal the appliance tenant. `None` means trusted, unscoped access within that tenant. A wrong type raises `TypeError`; a tenant mismatch raises `TenantNotFoundError`.
- `as_of`: optional integer timestamp passed to retrieval validity filtering. It is an advanced history selector, not a complete transactional snapshot across graph, local files, and all optional agents.

The same question need not produce identical results across installations: model discovery, indexed data, typo vocabulary, optional modes, checkpoints, local state, and runtime versions matter. Creative selection can vary even on one installation.

## Result routing for an agent

There is no single universal `success` or `verified` flag. Read the following layers separately:

1. **Transport/access/execution:** catch typed exceptions from Python, or inspect HTTP status. Check returned `error`, `access_error`, `__partial__`, and `__node_error__` before assuming a normal result. A graph failure can return a partial dictionary without `reply`. Empty caller scope returns a non-answer dictionary with `access_error="allowed_sources_empty"`, empty `related`, and no query encoding; HTTP may still be 200.
2. **Delivery:** inspect `guard_decision`, `delivery_blocked`, `shine_enforced`, and `shine_ok`. Treat explicit holds as authoritative. Do not use debug candidates to reconstruct a withheld response.
3. **Actual response producer:** examine `reply.situation`, `reply.draft`, `model01`, `frame_result`, `math_result`, `finance_result`, and `realization_result`. Optional keys can be absent. `reply.text` is the displayed string; `answer` can be narrowed or cleared by query assessment and can differ from the displayed specialist/Model01 result. `reply.body` is not a universal verification boundary.
4. **Evidence and limitations:** inspect producer-specific status, evidence, verification scope, and unresolved questions. A quote from an unrelated paragraph is not an answer. Candidate retrieval does not prove completeness or uniqueness.
5. **Application decision:** apply your own acceptance/approval policy after these checks. Do not convert a convenient displayed YES into an automated action without validating the queried proposition and source evidence.

A minimal integration can preserve these layers without manufacturing a single safety verdict:

```python
def response_view(result):
    reply = result.get("reply") or {}
    return {
        "error": result.get("error") or result.get("access_error") or result.get("__node_error__"),
        "partial": bool(result.get("__partial__")),
        "held": bool(
            result.get("delivery_blocked")
            or result.get("shine_enforced")
            or result.get("shine_ok") is False
            or result.get("guard_decision") not in (None, "allow")
        ),
        "display_text": reply.get("text", ""),
        "base_answer": result.get("answer"),
        "base_audit_passed": result.get("audit_passed"),
        "answer_status": result.get("answer_status"),
        "answer_evidence": result.get("answer_evidence") or [],
        "verification_scope": result.get("verification_scope"),
        "situation": reply.get("situation"),
        "draft": reply.get("draft"),
        "frame": result.get("frame_result"),
        "finance": result.get("finance_result"),
        "math": result.get("math_result"),
        "model01": result.get("model01"),
        "realization": result.get("realization_result"),
        "gather_questions": result.get("gather_questions") or [],
    }
```

This helper only organizes data. `held=False` or `base_audit_passed=True` is not proof that a rule conclusion, draft header, or learned wording is correct.

For recognized definition, named-attribute, present-action/location, weight, and source queries, also read `answer_status`. For example, the contract handles “What is the harbor kestrel?”, “Which city is the capital of France?”, “Where does the harbor kestrel nest?”, and “How much does the harbor kestrel weigh?”. `answered` means the query-binding checks found support in the audited base answer; it does not prove source truth or general semantic correctness. `insufficient_evidence` means the recognized relation was not found in the retrieved rows; `reply.text` is then “The retrieved passages do not settle that.” or “No passage was retrieved.” `conflicting` means the attribute matcher found distinct stored values and chose neither. `evidence_quote` means a binding sentence was retrieved but was not the audited answer, so the text is a passage preview. `answer_evidence` lists the document id and sentence for that status. `retrieved_candidates` lists what retrieval returned, including rows that do not support the claim. These fields are also copied into `reply`. `audit_passed` still covers the base proposition path, not every possible reply producer. `thinker_directive` is the thinker route; in the 18 October feature demonstration every prompt, including supported answers, stayed `gather`, so `gather` is not an abstention signal.

That contract does not cover arithmetic, event frames, ranking questions, or rule questions. Those keep their own producers. A checked sentence is not replaced by a rule reader that returns verdict `NONE`. See the [latest targeted review](reviews/2026-10-19/review-9d6fbe8.md) for verified fixes and the [18 October note](answerability-evaluation-2026-10-18.md) for the earlier, narrower comparison.

`reply.situation.verdict` can be `YES`, `NO`, `CONTESTED`, `UNKNOWN`, `CAUSE`, or `NONE`. The verdict follows the modality the question asks. “Is business class forbidden?” is NO when the passages show that it is allowed, and YES when the passages state that prohibition. “Is it required?” stays `UNKNOWN` when the passages only show an allowance. A rule that says something is allowed when a condition holds does not forbid the other cases and does not add the word “only”; those cases are `UNKNOWN`. A requirement whose condition does not hold is still reported as not required by that rule. Its `because` values are source **sentences**, not document IDs or source URLs. The current fact-bridge path may append background statements to its evidence pool; verify sentences against the original retrieved rows before treating them as citations. The current learned writer also lacks a candidate-verification call. See the [correctness handoff](handoff-claim-verification-review.md).

`frame_result` includes `status`, `text`, `verified`, evidence/gaps, and compatibility fields. A `verified` frame result refers to that frame transformation, not universal source truth. `realization_result` has its own status, mode, construction IDs, bindings, and verification fields; its verifier still has known construction-mutation gaps.

`related` uses `chunk_id`, usually with `chunk_text`, score/category. `passages` uses `document_id`. Keep identifiers alongside the exact evidence snapshot. `brief.sources`, draft sources, and realization evidence IDs have different scopes; do not concatenate them into a supposedly exhaustive citation list without normalization.

## Ingestion and lower-level calls

```python
from cpu_llm.documents import SourceDocument

document = SourceDocument("agent-notes", ("The harbor kestrel is a coastal falcon.",))
# With an existing app:
# receipt = app.ingest(document)
# ids = receipt["ids"]
```

`ingest` returns `documents`, `chunks`, `ids`, `connections`. Paragraph boundaries and normalized names determine IDs. Files opened by a reader generally use their stem; an explicitly supplied `SourceDocument` name that includes a suffix can retain that suffix in its normalized slug. Use the returned IDs and unique source names instead of reverse-engineering them.

`catalog_chunks(chunks, propositions=None, *, replace_prefix=None)` accepts `(document_id, text)` pairs and an optional dictionary of supplied EIR propositions keyed by ID, returning the chunk count. `index_chunks` is another lower-level write. Prefer `ingest` for ordinary source ingestion: directly passing strings/propositions through internal APIs is not equivalent to having the reader extract and validate every claim.

Do not let untrusted callers choose arbitrary server filesystem paths or broad replacement prefixes. The HTTP `source` form is a path on the **server**, not a client-side file upload. Paragraph bodies are an alternative to paths.

## Trusted caller scopes versus authentication

```python
from cpu_llm.access import CallerContext

caller = CallerContext.make(
    "tenant_alpha", "agent_a", ["agent-notes-p"], request_id="request-001"
)
# result = app.ask("What is the harbor kestrel?", caller=caller)
```

The scoped retrieval SQL accepts exact IDs or source prefixes ending in `-p`, then filters before dense ranking/LIMIT. Use `agent-notes-p`, not an informal prefix such as `agent`. `allowed_sources=[]` means no reads. The trusted Python API without `caller` is unscoped; it is not equivalent to an authenticated caller with an empty scope.

Direct `ingest` and `delete_source` do not take a caller argument. Authenticate and authorize writes through `Entry` or your own trusted boundary. Possession of a `CallerContext` does not prove authentication. Namespaces are application/schema isolation under one database credential, not independently provisioned PostgreSQL security principals.

## Authenticated HTTP service

Create a high-entropy bearer secret outside source control. For example, set it in `CPU_LLM_TOKEN` using your secret manager or shell. Generate the credential file from its digest without embedding the secret in the file:

```python
import json
import os
from pathlib import Path
from cpu_llm.entry import secret_sha256

credentials = {"credentials": [{
    "id": "agent_a",
    "caller_id": "agent_a",
    "tenant_id": "tenant_alpha",
    "allowed_sources": ["agent-notes-p"],
    "secret_sha256": secret_sha256(os.environ["CPU_LLM_TOKEN"]),
}]}
Path("credentials.json").write_text(json.dumps(credentials), encoding="utf-8")
```

Plaintext `secret` entries are refused. The service reads the credential file into `Entry` at construction; changing it does not reload an already running instance. Request authentication hashes the presented secret and compares digests using `hmac.compare_digest`.

```powershell
cpu-llm-serve --secrets credentials.json --host 127.0.0.1 --port 8765
```

Every route below is POST with a JSON object and `Authorization: Bearer <actual-secret>`. The process defaults to loopback; it has no built-in TLS, rate limiting, or production request-size/timeout policy.

- `/v1/ingest`: `{"name":"agent-notes","paragraphs":["The harbor kestrel is a coastal falcon."]}`; alternatively `{"source":"server/path/agent-notes.pdf"}`. This is JSON ingestion, not multipart upload. The credential must allow the source prefix.
- `/v1/ask`: `{"message":"What is the harbor kestrel?"}`. Additional forwarded fields are exactly `discover`, `imagine`, `deep`, `math`, `finance`, `as_of`. Other Python `ask` arguments are not exposed by this route; extra JSON keys are not forwarded.
- `/v1/correct`: `document_id`, `prior_sentence`, `new_sentence`, `actor_id`, and required integer `timestamp`. Supply the exact previous wording and actual document ID. The authenticated source scope is checked.
- `/v1/delete`: `{"source":"agent-notes"}` deletes a whole source prefix, not one paragraph.

Example request using the standard library:

```python
import json
import os
import urllib.request

request = urllib.request.Request(
    "http://127.0.0.1:8765/v1/ask",
    data=json.dumps({"message": "What is the harbor kestrel?"}).encode("utf-8"),
    headers={
        "Authorization": "Bearer " + os.environ["CPU_LLM_TOKEN"],
        "Content-Type": "application/json",
    },
    method="POST",
)
with urllib.request.urlopen(request, timeout=60) as response:
    result = json.load(response)
print(response_view(result))
```

Run ingestion first. `response_view` is the helper above. Set a client timeout appropriate to encoder startup and the request; the service does not make every turn finish within a fixed duration.

Mapped errors return `{"error": code, "message": text}`: authentication failures use 401; source/tenant/access refusals 403; storage errors 503; caught `ValueError` requests 400. An unserved path currently yields 400, not 404. Unexpected exceptions are not universally wrapped into this JSON contract. `urllib` raises `HTTPError` for non-2xx responses; read its body to inspect a mapped error, and distinguish it from a timeout/connection failure.

The service caches one appliance per tenant and forwards to ordinary `ask`. It does not route through `ask_concurrent`. Coordinate concurrent requests, shared follow-up state, and writes explicitly rather than assuming a threaded HTTP server establishes safe multi-session behavior.

## Corrections and history

```python
# Existing app and an actual returned document ID:
# receipt = app.correct(
#     document_id, prior_sentence, new_sentence,
#     actor_id="agent_a", timestamp=1792281600, caller=caller,
# )
# historical = app.ask(question, caller=caller, as_of=earlier_timestamp)
```

The timestamp is an integer Unix timestamp in seconds. The prior text must match the currently located live graph node. Replacement text must round-trip through the proposition realizer. The receipt includes `new_id`, actor/timestamp, and `prior_kept`; retain it. Reusing a correction ID/timestamp raises rather than silently replacing the correction.

The code appends a graph node and SUPERSEDES edge, retires a vector interval, and saves the new vector row. These are multiple writes without a single cross-store transaction. Do not promise atomic rollback or a complete historical snapshot; verify corrected/historical retrieval on your deployed instance, including process restart. Exact paragraph scopes may need updating for newly versioned IDs; source-level `-p` scopes include version suffixes.

`delete_source` removes vector/graph/word-index entries by source prefix and leaves resonance and shared word relations unchanged. It is distinct from a correction, is not a tombstone, and does not establish deletion from every secondary artifact or external backup. Inspect `nodes_remaining` and the returned counts.

## Concurrent calls and capacity outcomes

`ask_concurrent(message, *, request_id=None, caller=None, thinker_factory=None, **kwargs)` runs synchronously on an assigned local seat and passes `kwargs` to `ask`. It does not itself return a Future. `thinker_factory` is an advanced/test hook; ordinary consumers should retain the default.

Successful results add `seat` and `request_id`. `other_server` means the turn was not executed on another server; arrange external routing or backpressure. `seat_failed` is a request failure, not an abstention. Failed work may require reconciliation before retrying any writes. Follow-up state and other mutable stores are still shared at the appliance level; this path is experimental rather than a blanket thread-safety guarantee.

Capacity byte accounting and remote-fabric frames are not proof of an actual distributed database or deployed worker. See the outstanding capacity findings in the handoff before relying on autoscaling decisions.

## Finance inputs

The pure `cpu_llm.finance.validate_message(message, *, forced=False)` returns `triggered`, `reasons`, `products`, `text`, and `checks`. It does not need PostgreSQL and does not initialize an appliance. Inspect each check's `completed`, `verdict`, and limitation fields where provided; dispatcher-level `triggered=True` does not mean the input was valid or accepted.

Product inputs can be labeled lines or JSON embedded in the message. A JSON form can use a `product` field or nested `refundproof`, `ledgercovenant`, and `ledgerlock` sections. Do not turn numeric strings into binary floats before passing them to the validators. Labeled values remain text.

- RefundProof: supplied vendor/invoice/tax/evidence/rule/approval data; no external registration, filing, recovery, or human approval is performed by this library call.
- LedgerCovenant: supplied figures, precedence, thresholds, and relevant provisions; an absent or ambiguous figure is not filled from external records.
- Ledgerlock: supported document type, document text, field ID/value/confidence, and character offsets. For `Wages 84210.00`, the matching span is `[6:14]`. The digest is SHA-256 of the decision data, not an Ed25519 signature or proof that the underlying document is authentic.

Canonical behavior and concrete valid/invalid inputs are in [test_finance.py](../tests/test_finance.py) and the corresponding [finance modules](../src/cpu_llm/finance/). User-visible financial conclusions need their domain-specific review; this interface describes local validation, not an external authority decision.

## Validation and troubleshooting

The complete suite requires the PostgreSQL service, cached/downloadable encoder assets, writable temporary storage, and for service tests permission to bind a local port. Optional fact-bridge model tests may skip or run according to installed checkpoints.

For the documentation update, a focused run of frames, answering, N0, access, enterprise helpers, finance, documents, and tenant-isolation tests produced **70 passes and two tenant-isolation failures caused by sandbox-denied PostgreSQL connections**. This is not a full-suite or live-isolation pass. See the historical suite records for other environments; do not reuse their counts as a fresh result.

Common distinctions:

- Constructor/database error: infrastructure or permission failure, not a semantic unknown answer.
- Empty `related`: no candidates in the selected tenant/scope, not proof no such fact exists anywhere.
- `needs_evidence_propositions`: retrieved text lacks a supported stored proposition; a quote can still be displayed.
- Wrong namespace or working directory: the CLI and Python instance may be reading different tenant/cache state.
- Unexpected local-model load: inspect `FACTBRIDGE_MODELS` and the package-root model directories. An invalid override does not disable lookup of later fallback locations.
- Missing dependency/checkpoint on automatic ML fallback: a deployment provisioning issue; setting `realization="deterministic"` is not currently a reliable disable switch for that separate path.
- Rejected output: retain the returned non-answer/hold. Do not retry by stripping safety fields or changing a failed verification flag.

See [the review handoff](handoff-claim-verification-review.md) for specific unresolved correctness defects. Documentation should identify them rather than imply they were repaired by changing the README.
