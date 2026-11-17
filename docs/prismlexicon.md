# PrismLexicon specification

Status: experimental, disabled by default.

```text
Request → existing retrieval and reasoning → existing evidence audit and rendering
        → PrismLexicon display adapter → reply delivery
```

The adapter uses the public delivery boundary so the existing audit and output
renderers remain authoritative. It only adapts eligible plain-text answers.
Evidence quotes, research, strict, specialist, multi-task, and structured
rendered responses retain their original delivery. The API retains canonical
answer fields, evidence and receipts, and saves the pre-edit display text as
`reply.original_text` when an edit is applied.

## Request and response

- Python: `Appliance(prismlexicon=True)` and `ask(prompt, target_level="A2")`.
- HTTP: start `cpu-llm-serve --prismlexicon ...` and send `target_level` to `/v1/ask`.
- Prompt: append “Use simple English.” after a question, or use “Use CEFR A2
  English.” An explicit API level takes precedence. The control is removed
  before question processing when it is recognized.
- Use `off` per request or disable the appliance/server flag for rollback.

The `prismlexicon` receipt includes the requested level, versioned rule source,
sense IDs, input/output offsets, decisions and protected-span integrity status.
A1 through B1 and auto use the same conservative plain-language policy. B2
through C2 currently abstain. These are policy inputs. The original reviewed
rules have unknown CEFR difficulty, and this pilot makes no full-text CEFR
readability claim. Glossary output is deferred.

## Rule and protection model

The small original Apache-2.0 rule set records source and target senses, POS,
gloss, a context pattern and approved surface form. Examples distinguish a
bright light from a bright student, preserve the tense and agreement of
geographic residence, and simplify the temporal phrase “prior to.” Unmatched
senses retain their wording. Exact evidence spans and recognized quotation,
citation, URL and code spans are locked. Edits are confined to the approved
surface forms, so numbers, units, other identifiers, and modality markers are
copied. After applying edits, the adapter verifies locked spans and rolls back
on a mismatch. Work is capped at 16,000 characters and 16 applied changes.
There are no network calls or persistent text logs.

See the [resource audit](prismlexicon-audit.md) and
[pilot evaluation](prismlexicon-evaluation.md).
