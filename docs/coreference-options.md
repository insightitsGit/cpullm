# Scenario 2: reference resolution research

Researched 2026-10-25. These were the initial candidate notes. Implementation
has since added optional Coreferee and Fastcoref adapters, session-local reference
state, and clarification. Coreferee has real CPU smoke validation in an isolated
build directory; Fastcoref has not been model-tested. See
[current usage and limits](reference-resolution.md). No broad performance or
accuracy benchmark has been completed.

## What the tagging needs to do

POS tagging identifies grammatical roles; named-entity recognition identifies
entity mentions. Neither alone links "it" to "European lobster". Coreference
resolution groups mentions referring to the same entity. Cross-turn use also
requires our own bounded conversation history and session isolation.

Example target, not an observed model result:

- Prior turn: "Tell me about the European lobster."
- Current turn: "Where does it live?"
- Candidate binding: "it" -> "the European lobster".
- Retrieval prompt: "Where does the European lobster live?"
- Original prompt and binding offsets/provenance remain available.

## Candidates

### Coreferee

MIT-licensed spaCy extension. Its current README lists Python 3.10-3.13,
spaCy 3.7-3.8 support, and English/French/German/Polish. It combines linguistic
rules with a neural ensemble to build reference chains. Candidate to evaluate
for the CPU-oriented library; actual latency, accuracy, model downloads, and
compatibility with installed packages remain unverified.

Source: https://github.com/richardpaulhudson/coreferee

### Fastcoref

MIT-licensed package with reference clusters, character offsets, pair logits,
and spaCy integration. Official documentation shows CPU configuration. The
F-COREF model card also declares MIT licensing. It is a useful comparison
baseline; published GPU timings are not evidence of CPU speed here. The
current repository dependency requirements need an isolated compatibility
check before changing our environment.

Sources:
- https://github.com/shon-otmazgin/fastcoref
- https://github.com/shon-otmazgin/fastcoref/blob/main/pyproject.toml
- https://huggingface.co/biu-nlp/f-coref

### spaCy experimental CoreferenceResolver

Official component in `spacy-experimental`, not spaCy core. Stores token
clusters in `Doc.spans`; a SpanResolver can expand them to mention spans.
Candidate for a more customized pipeline; adding the component alone is not
a substitute for loading/training suitable model weights.

Source: https://spacy.io/api/coref/

## Proposed integration boundary

1. Maintain caller/session-local recent turns; never combine tenants or sessions.
2. Give the resolver only authorized context plus the current prompt, retaining
   speaker/turn boundaries in our context representation.
3. Accept only a binding to a concrete mention present in that context. Preserve
   candidate spans and provenance. Pair logits are not calibrated probabilities.
4. If several antecedents remain plausible, leave the reference unresolved and
   request clarification rather than silently choosing the nearest noun.
5. Apply accepted bindings to the current prompt before dictionary interpretation,
   prompt embedding, channel intent routing, and retrieval. Preserve original text.
6. A reference hypothesis is conversational metadata, not a permanent knowledge
   graph fact or new evidence about the world.

Test cases should include a single entity; two competing entities; topic changes;
plural pronouns; "that lobster"; "this" referring to a whole event; missing
antecedents; negation; and concurrent isolated sessions. Coreference will not
by itself resolve whether "Can I eat it?" asks about edibility, permission,
or safety. That is a separate intent distinction.

Implemented since this research: Coreferee and Fastcoref adapter interfaces,
session-local prompt context, ambiguity clarification, and explicit confirmation.
Coreferee has real CPU smoke validation and is the primary tested option.
Remaining evaluation: broader accuracy, CPU latency/memory, and real Fastcoref
model inference. See [the current implementation](reference-resolution.md).
