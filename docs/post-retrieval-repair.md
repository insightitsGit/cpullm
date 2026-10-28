# Post-retrieval repair and intent confirmation

Implemented 2026-10-28. This is a bounded extension of the existing request,
retrieval, judgment and clarification pipeline, not arbitrary English correction.

## Execution

The existing attribute repair retains its maximum three queries and five hits
per query. Definitions and type questions now also use it, searching for identity,
definition, type and role evidence. The original factual question remains unchanged.
Definition repair does not inherit a type's attributes as an individual's identity.
An already settled or ambiguous definition does not trigger more repair. Scope and
as_of are forwarded to every repair search, with returned IDs filtered by scope.

After final delivery judgment, `inspect_gap` examines an insufficient-evidence
outcome and the same permitted retrieved rows. It distinguishes two cases:

- A clear requested relation lacks facts: preserve insufficient evidence and return
  `post_retrieval.reason="missing_evidence"`. Do not force a different question.
- A broad `What is X?` definition lacks a definition but retrieved text supports
  another recognized relation: ask the user to confirm an interpretation. Never
  answer the alternative silently.

Options include an explicit identity confirmation (`Who is X?`) and up to three
source-backed alternatives from past/current activity, location, color, possession
and lifespan. Candidate questions are evaluated locally against retrieved rows;
listing an option does not itself execute another search or endorse an answer.
The ordering is deterministic, not a calibrated likelihood ranking. Identity may
still have missing evidence: choosing it cannot create a role or occupation.

No alternatives are invented for an unknown entity with no supporting facts.
Explicit `Who is X?`, kind, color, lifespan and other clear slot questions remain
missing-fact outcomes when unsettled. Conflicts, blocked/unsupported requests,
partial graph execution, delivery/grounding holds and specialist producers do
not become this clarification loop. Existing sense/reference/criteria flows retain
ownership of their ambiguities.

## Example

Stored text: `Mary baked a cake.`

`What is Mary?` cannot use that action as a definition. After bounded definition
repair fails, it offers `Who is Mary?` and `What did Mary do?`. A number, exact
label (`identity` or `activity`) or full offered question confirms the choice.

Choosing identity reruns that question and returns insufficient evidence if no
identity is stored. It does not repeatedly ask the same interpretation question.
Choosing activity reruns retrieval/assessment and may quote the action. It never
derives `Mary is a baker` from baking. The same mechanism can offer a location,
color, possessions or lifespan question when those facts are present instead.

Activity support is an affirmative main clause whose first word is a finite
verb of the asked agreement. "What did" takes a regular past or a declared
irregular past, including found, said, saw, came, and left. "What does" takes
the third-person present. "What do" takes the base form, so a plural subject
can answer. A modifier in front of a later finite verb, such as "baked goods
are" or "colored glass is", is not an action. "Lives in" and "lived for"
stay with residence and lifespan. Roles, possession, negation, conditionals,
modals, and other subjects do not satisfy an activity request. This quotes an
observed action. It does not infer an occupation, and an unrecognized
construction can still require the user to rephrase.

## Conversation and public contract

The existing `ClarificationLoop` stores the interpretation stage under its scoped
session key. TTL, size/attempt bounds, cancellation, new-question abandonment and
caller/history isolation apply. Numbers and labels are explicit choices; an
ambiguous `yes` does not select one. The full offered question counts as a choice;
an unrelated new question abandons the pending plan.

Without `session_id`, no choice state is stored and the reply asks the user to
send the full intended question. No source text is ingested from a confirmation.
In compound requests, the parent stops at the clarification, marks later tasks
pending, and resumes the confirmed child before the remainder. Parent response
budgets survive. If selected retrieval later lacks evidence, it stays missing.

`post_retrieval` exposes schema `post-retrieval-gap-v1`, requested entity/relation,
reason, confirmation state and suggested questions. An interpretation clarification
returns `answer=None`, empty accepted evidence, `audit_passed=False`, and a
clarification judgment rather than the unrelated rejected answer. Existing
`attribute_search` metadata retains the repair trace when present.

The loop uses the existing final evidence judgment. It does not add another
PrismThinker call or claim that Thinker can infer absent facts from raw text.

## Validation and limits

Focused tests cover multiple names/actions, role-versus-event distinctions,
supported alternative relations, identity confirmation without inference,
stateless calls, missing evidence, caller isolation, cancellation, expiration,
attempt bounds, scoped/historical definition repair, held outcomes and compound
continuation with a number or full question. Public `ask()` tests substitute the
retrieval/graph to exercise orchestration; index tests use controlled search
results. These do not establish live PostgreSQL/encoder behavior or a new accuracy
benchmark. Full live validation and an independent evaluation remain necessary.
