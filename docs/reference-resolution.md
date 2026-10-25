# Optional CPU reference resolution

The ranking clarification loop now connects to a separate reference-resolution
stage before dictionary interpretation, query embedding, and intent routing.
Accepted bindings rewrite only the current query. The response preserves
`original_message`, `resolved_query`, and `reference_resolution` (mention offsets,
antecedent text, backend/provenance). Reference hypotheses do not become facts.

## Coreferee setup

Coreferee is the primary tested adapter. Install it and its trained English
models in your application environment, explicitly:

```powershell
python -m pip install -e ".[coreference]"
python -m spacy download en_core_web_sm
python -m coreferee install en
```

```python
from cpu_llm.pipeline import Appliance

app = Appliance(reference_backend="coreferee")
app.ask("Tell me about the European lobster.", session_id="chat-1")
result = app.ask("Where does it live?", session_id="chat-1")
# Accepted binding produces: Where does the European lobster live?
```

Coreferee and spaCy run on CPU. Reference spans come from Coreferee's chains;
prior noun phrases are recovered through spaCy parsing. A nominal "that lobster"
can also use a unique matching prior noun rule, which handles small-parser
tagging errors. Competing compatible antecedents trigger clarification even if
the model prefers one. Standalone event references such as "Why did this happen?"
are deliberately not guessed as entity references.

## Alternative and degraded operation

`reference_backend="fastcoref"` uses a second adapter, configured for CPU;
install `.[fastcoreference]` and the spaCy English model first. It can download
its model on explicit backend construction. This adapter's real model has not
been validated in this workspace; Coreferee has. A custom adapter implementing
`analyze(context, prompt)` may also be supplied to `ReferenceSessions` or Appliance.

The default backend is `None`: no automatic model download or new mandatory
dependency. References then trigger clarification rather than nearest-noun
guesses. The user can confirm a full entity name, or restate the full question.
The HTTP service accepts `--reference-backend coreferee` or `fastcoref` at startup.
Use the same explicit `session_id` on every related `/v1/ask` request.

## Context and failure handling

Context contains only the latest user/resolved prompt (up to 4,000 characters),
not retrieved documents or generated answers. It is isolated by tenant, caller,
allowed-source scope, session ID, and historical timestamp. There is no implicit
cross-request session. State expires after 30 minutes, is capped at 256 sessions,
and unresolved-reference questioning stops after three attempts. `cancel` or
`start over` clears reference state. A full new question abandons the pending
reference; an exact candidate name resumes it with user-confirmed provenance.

Possessives retain the possessed noun; plural pronouns require compatible plural
antecedents. Model failures and ungrounded or partial bindings ask for clarification.
Original text remains available, and existing downstream guard/audit holds remain
authoritative. Session turns should be submitted in order. Startup model-loading
errors surface explicitly rather than pretending that a model was available.

This is conservative reference resolution, not arbitrary conversation understanding.
Resolving "Can I eat it?" identifies the referent; edibility versus permission
versus individual safety still needs its own intent policy and evidence.

## Local validation

Coreferee 1.5.0 and its English models, with spaCy `en_core_web_sm` 3.8.0, were
installed only in ignored `build/coreference-deps` for real CPU smoke tests.
The default/global Python installation was not changed. Singular `it`, plural
`they`/`them`, possessive `its`, a person pronoun, and an explicit nominal reference
were exercised. Two lobster candidates correctly produced clarification.
Performance and broad-domain accuracy have not been established.
