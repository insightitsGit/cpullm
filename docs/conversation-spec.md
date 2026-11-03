# Built-in conversation node, version 1

The default reviewed pack handles eight intents: greetings, wellbeing,
identity, capabilities/help, thanks, farewells, limitations and model identity.
It contains original cpu-llm application responses and 51 complete-turn input
phrases. No external assistant answers, persona records or medical facts are
bundled. Its JSON file is included in the installed package.

## Routing and output

`Appliance(..., small_talk=True)` is the default. `ask(..., small_talk=False)`
disables the feature for a request. A constructor disable cannot be overridden
by a request. The HTTP JSON body accepts a boolean `small_talk`; service
`--no-small-talk` enforces disable for all requests. Authentication, tenant
checks and the raw-prompt guard remain in force.

The pre-graph `conversation.reply` node matches a complete reviewed phrase
after bounded Unicode/case/whitespace and terminal-punctuation normalization.
Quoted/code text, longer questions and content containing extra instructions
are not whole-turn social matches. There is no embedding nearest-neighbor
fallback and no learned generation. Package identity comes from this application's
own pack, never another assistant's dataset persona.

Social output uses `answer_status="conversation"` and
`response_kind="conversation"`. `answer` is null, `answer_evidence` is empty
and `audit_passed` is false. `conversation` records the intent, built-in policy
origin, pack schema/hash, selected tone, lack of document/clinical verification
and stateless execution. Clients must recognize this as a social response,
not a document-grounded answer. It does not create or consume session memory.

Python `style="friendly"` and `style="formal"` select reviewed variants.
Other valid tone controls use labeled neutral fallback. Weighted preferences
choose the highest-weight permitted tone deterministically; relationship-risk
conflicts use neutral wording. These are pack variants, not a new invocation
of the factual stylistic generation/verifier node. The HTTP service still does
not expose style selection.

## Mixed prompts and strict policy version 3

A leading greeting/thanks followed by a substantive request is normalized to
the entire remaining request only after guarding the raw message. Thus
`Hi, can I take Fictional Luma?` still reaches strict unsupported/advice handling.
The greeting never supplies an answer to the medical question. The returned
`original_message` and `conversation_prefix` preserve the original text, exact
prefix offsets and engine query. Negation, conditions and extra questions in
the remaining text are not removed. This is greeting-prefix normalization,
not arbitrary mixed-intent planning; multi-question identity/factual prompts
can still exceed supported forms.

Strict policy `strict-evidence-v3` adds the explicitly typed
`builtin_conversation` scope for pure social turns. It does not grant document
proof or clinical validation. Strict factual requests retain their existing
quotation/arithmetic/abstention path; no FLAN-T5 or other generator is enabled.
Strict capabilities text names the actual strict limitations. To preserve a
deployment's prior evidence-only behavior, disable small talk at the appliance
or service level. Unsupported social phrasing is not guessed.

## External datasets: candidate preparation only

`tools/prepare_conversation_candidates.py` reads a **local JSON/JSONL export**
and prepares a deduplicated review queue. It requires an upstream revision SHA,
records the input hash and declared source/license, and never authenticates a
file's asserted upstream identity. It makes no network request, executes no
remote dataset loader, trains no model and changes no runtime pack or facts.

- [OpenAssistant/oasst1](https://huggingface.co/datasets/OpenAssistant/oasst1):
  its card lists Apache-2.0. Only reviewed, undeleted English prompter records
  without a positive supplied PII label are considered. Assistant messages are
  ignored.
- [HuggingFaceH4/ultrachat_200k](https://huggingface.co/datasets/HuggingFaceH4/ultrachat_200k):
  its card lists MIT and describes synthetic dialogue. Only the first user
  message is considered; assistant content is ignored.
- [DailyDialog](https://huggingface.co/datasets/li2017dailydialog/daily_dialog):
  its card lists CC BY-NC-SA 4.0. It is not bundled or enabled for import by
  default; the tool requires `--allow-noncommercial` acknowledgment. That flag
  does not grant additional usage rights.

These source-card observations were checked November 2, 2026. Review the pinned
source and applicable terms before importing or redistributing actual data.
No upstream dialogue data was downloaded or redistributed with this feature.

```powershell
python tools/prepare_conversation_candidates.py --input local-oasst.jsonl --source OpenAssistant/oasst1 --revision <40-character-upstream-sha> --out candidates.json
```

Only phrases already recognized as pure built-in intents are emitted, marked
`reviewed=false`; new/unknown phrasing is not silently assigned a social intent.
The queue helps inspect source coverage. Expanding runtime coverage requires an
explicit review, pack edit and regression tests for substantive-question capture.
Candidate records cannot install an external assistant identity or turn dataset
answers into source evidence. Exports are capped at 128 MiB and scans at a
declared record limit. The output file must be new.

## Tests and limits

Tests cover whole-turn aliases, original identity, controlled variants,
relationship restrictions, raw-prompt guard, tenant isolation, disable precedence,
strict metadata, greeting offsets, mixed medication requests, candidate filters,
license acknowledgment, real HTTP controls and real source-scoped strict lookup.
This pack does not supply open-domain factual knowledge, unrestricted dialogue
reasoning, emotional experience, professional qualifications or clinical safety.
