# Clarification before subjective rankings

The first dialogue loop handles `best`, `worst`, `better`, and `worse` requests.
It does not infer the user's criteria from retrieved neighbors or a generic
ranking. General ambiguity, model-assisted dialogue, and reference resolution
remain separate work.

## Example

```python
app.ask("Which lobster is best?", session_id="chat-1")
# needs_clarification: What does best mean for you, and what is it for?
app.ask("taste", session_id="chat-1")
# Retrieves with the original question plus the explicitly supplied criterion.
# If no supporting comparison is found: asks for comparison data or a source.
app.ask("Source: ...", session_id="chat-1")
# Quotes an applicable user-supplied ranking with user-provided attribution,
# or reports that the information still does not settle the question.
```

`needs_clarification`, `clarification.slot`, `status`, `user_criteria`, and
`resolved_query` make the loop reviewable. Early clarification has `answer=None`
and performs no embedding or database retrieval. A ranking can be quoted only
when a source sentence explicitly states an order, names the topic, and includes
the supplied criterion terms. This deliberately conservative lexical check
does not provide a general comparison calculator or entailment model. Quoted
source statements are not certified truths, and user-provided text is never
automatically ingested into the permanent knowledge graph.

Use the same explicit `session_id` for subsequent turns. State is keyed by tenant,
caller, allowed-source scope, session ID, and historical timestamp. Without a
session ID, no pending state is retained: restate the complete question with its
criterion. HTTP `/v1/ask` forwards `session_id` through authenticated Entry calls.
Pending state is in process memory, expires after 30 minutes, and is capped at
256 sessions. Each clarification stage has a three-question limit; `cancel`,
`start over`, or a full new question abandons the pending request. State is lost
on process restart. Concurrent turns within a single session should be submitted
in order by the caller; operations are locked but semantic turn order is not guessed.

Source access checks run before clarification. Later guard, audit, grammar,
and Shine holds cannot be overridden by a clarification or supplied source.
Conversational criteria are preferences, not evidence about which option wins.
