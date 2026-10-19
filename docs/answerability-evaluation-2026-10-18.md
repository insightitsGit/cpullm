# Answerability check, 18 October 2026

This note records one checked contract, not a claim that cpu-llm answers arbitrary questions.

The question is: given only the sentences supplied to the turn, does the reply state the relation the question asks for, cite that sentence, and say when the sentences do not settle it? The check does not fill a gap from model knowledge. “Paris” is spoken for “What is the capital of France?” only when a supplied sentence states that relation.

## What was already in the tree

`src/cpu_llm/ranking.py` answers a different question: whether a stored sentence states an order such as best, worst, or ranked. It does not decide that a passage answers “What is the capital of France?” On the seven-paragraph corpus below, that ranking code leaves the old reply in place.

The saved feature demonstration asked that question and received “The harbor kestrel is a small coastal falcon. it eats small fish. Business class is allowed for flights over six hours.” with `audit_passed` true and `shine_ok` true. Those flags meant the spoken sentences matched stored propositions. They did not mean the sentences answered the question. `thinker_directive` was `gather` for every prompt in that run, including prompts that were answered, so the fix does not treat `gather` as a refusal.

## Contract covered here

The binder owns three shapes:

- “What is …” / “Who is …” and the past forms with was/were.
- “What is France's capital?” and “Which city is the capital of France?”
- “Cite sources for …”

A sentence answers an attribute question only when it states that attribute of that entity in the question’s tense, as an affirmative claim, and not under “if”. Sharing “France”, “capital”, or both is not enough. A definition or source question uses sentences whose subject is the asked name, including an explicit “known as” alias. “France Area” does not count as “France”.

Arithmetic, event frames, ranking questions, and rule questions stay with their own producers. A rule reader that returns verdict `NONE` does not erase a sentence the base path already checked.

`answer_status` is separate from `audit_passed`:

| Status | Meaning |
| --- | --- |
| `answered` | The spoken sentences state the relation, and the base audit accepted them. |
| `insufficient_evidence` | Nothing retrieved states it. The reply says the passages do not settle it, or that no passage was retrieved. |
| `conflicting` | More than one value is stored. The reply quotes them and does not pick one. |
| `evidence_quote` | A binding sentence was retrieved but was not the audited answer. The text is labeled as a passage. |

`answer_evidence` is the cited id and sentence. `retrieved_candidates` is the shortlist, including rows that are not citations. `verification_scope` is `query` for a bound answer or a refusal, and `retrieval` for a passage preview.

## Frozen comparison

The same 17 fixtures are scored three ways. Six are answerable, nine are not, and two are conflicts (the same Paris/Lyon pair in both orders). The fixtures are the assertions in `tests/test_answerability.py`. They were written with this patch, so they are a contract test, not a held-out customer corpus. Latency was not measured here.

- **Baseline A** labels the first passage as a passage and never calls it an answer.
- **Baseline B** speaks the first passage as the answer whenever one was retrieved.
- **Candidate** is `assess` in `src/cpu_llm/answerability.py`, the evidence-binding step. Delivery then requires the base audit before `answer_status` is `answered`.

| | Answerable covered | Unsupported answers on the 9 unanswerable items | Conflicts left unresolved | Citations whose span is the cited sentence |
| --- | --- | --- | --- | --- |
| Baseline A | 0 / 6 | 0 | 0 / 2 | 0 |
| Baseline B | 5 / 6 | 8 | 0 / 2 | 5 |
| Candidate | 6 / 6 | 0 | 2 / 2 | 6 |

Baseline A never states an unsupported capital, and it also never answers. Baseline B answers five of the six answerable items because the useful sentence happened to be first, and it states an unsupported answer on eight of the nine unanswerable items. The candidate answers all six, abstains on all nine, and quotes both sides of both conflict orders. On the motivating item the first passage is about a kestrel; only the candidate abstains.

The seven paragraphs are:

1. The harbor kestrel is a small coastal falcon.
2. The harbor kestrel nests in coastal cliffs.
3. The harbor kestrel eats small fish.
4. John ate a yellow apple in his house.
5. Business class is allowed for flights over six hours.
6. The flight from Boston to Paris takes eight hours.
7. The flight from Boston to Chicago takes two hours.

“What is the capital of France?” against those paragraphs yields `answer_status=insufficient_evidence` and “The retrieved passages do not settle that.” Adding “The capital of France is Paris.” yields that sentence and its id. “Paris is the capital of France.” together with “Lyon is the capital of France.” yields neither city as the chosen answer.

## Live check

On 18 October 2026 the local `cpullm-pgvector` database was up. Two fresh namespaces each received the seven paragraphs through `Appliance.ingest`. No existing source was edited.

Against the seven paragraphs, `ask("What is the capital of France?")` returned `answer_status` `insufficient_evidence`, `answer` null, `audit_passed` null, and reply text “The retrieved passages do not settle that.” After `The capital of France is Paris.` was ingested, the same question returned that sentence, `answer_status` `answered`, `audit_passed` true, and evidence id `capital-note-p0001`.

`ask("What is the harbor kestrel?")` returned “The harbor kestrel is a small coastal falcon. it eats small fish.” with status `answered`. The evidence id on that reply was `feature-notes-p0001` only: the second spoken clause is the pronoun “it eats small fish,” and that clause is not paired with `feature-notes-p0003`. `ask("Cite sources for the harbor kestrel.")` listed `feature-notes-p0001`, `feature-notes-p0003`, and `feature-notes-p0002`. The two flight paragraphs were not in that list.

Each of those two processes returned in about 12 seconds, including process startup. That is not a latency comparison.

## What this does not show

The 6/6 and 0/9 figures are this fixture list. They are not a recall number for Wikipedia, the WikiText index, or a customer corpus. Word overlap is still not semantic entailment. Questions outside the three shapes above are unchanged. A source can be faithfully quoted and still be false. No new model was trained.
