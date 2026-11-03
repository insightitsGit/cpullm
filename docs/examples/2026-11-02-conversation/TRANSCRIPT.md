# Default conversation: actual 12-turn demo

Executed November 2, 2026 on committed runtime `dcb24ab`. All **12/12** expected
status/routing checks passed. The application used a new local PostgreSQL
namespace, cached model assets, strict evidence mode and a source-restricted
caller. No external dialogue dataset or hosted model was used. The single
label fact is fictional software test data, not medication guidance.

Social replies are original built-in policy text, not source quotations or
clinical advice. The records below are actual API output. Each is an independent
request; no conversational memory is inferred from this transcript.

## 1. Hello!

> Hello! What would you like to know?

Status: `conversation`; check: **PASS**.
Origin: `builtin_policy`; tone: `neutral`; alignment: `supported`.

## 2. Who are you?

> I'm cpu-llm, a local assistant for supported questions about your documents and explicit rules.

Status: `conversation`; check: **PASS**.
Origin: `builtin_policy`; tone: `neutral`; alignment: `supported`.

## 3. How are you?

> I'm ready to help. What would you like to know?

Status: `conversation`; check: **PASS**.
Origin: `builtin_policy`; tone: `neutral`; alignment: `supported`.

## 4. What can you do?

> Strict evidence mode can quote supported source facts, check recognized conflicts, and perform bounded exact arithmetic. Unsupported requests receive a nonanswer.

Status: `conversation`; check: **PASS**.
Origin: `builtin_policy`; tone: `neutral`; alignment: `supported`.

## 5. Who are you?

API options: `{"style": "formal"}`.

> I am cpu-llm, a CPU-based document question-answering and rule-checking library.

Status: `conversation`; check: **PASS**.
Origin: `builtin_policy`; tone: `formal`; alignment: `supported`.

## 6. Hello!

API options: `{"style": "poetic"}`.

> Hello! What would you like to know?

Status: `conversation`; check: **PASS**.
Origin: `builtin_policy`; tone: `neutral`; alignment: `neutral_fallback`.

## 7. Thanks!

> You're welcome.

Status: `conversation`; check: **PASS**.
Origin: `builtin_policy`; tone: `neutral`; alignment: `supported`.

## 8. Goodbye.

> Goodbye. You can return whenever you need help.

Status: `conversation`; check: **PASS**.
Origin: `builtin_policy`; tone: `neutral`; alignment: `supported`.

## 9. Hi, What is the strength of Fictional Luma?

> Source quotations (not clinically validated):
> [conversation-demo-p0001] The strength of Fictional Luma is 0.75 mg.

Status: `evidence_quote`; check: **PASS**.
The greeting prefix was removed only after guarding the raw input; the remaining question used strict evidence routing.

## 10. Hello, can I take Fictional Luma?

> Unsupported strict request; use explicit named attribute questions.

Status: `unsupported`; check: **PASS**.
The greeting prefix was removed only after guarding the raw input; the remaining question used strict evidence routing.

## 11. Who are you?

API options: `{"small_talk": false}`.

> Unsupported strict request; use explicit named attribute questions.

Status: `unsupported`; check: **PASS**.

## 12. The document says "hello".

> Unsupported strict request; use explicit named attribute questions.

Status: `unsupported`; check: **PASS**.

## Reproduce and inspect

Run `python examples/conversation/run_demo.py --out build/conversation-demo-new-run`
from the checkout after normal setup. The output directory must be new. See
[demo setup](../../../examples/conversation/README.md) and
[the contract](../../conversation-spec.md).

`responses.json.gz` retains full results, `receipt.json` pins runtime/input/runner
hashes, and `artifact-hashes.json` protects saved bytes. The archive includes the
891-pass full-suite log and offline wheel packaging/install logs. After one
additive metadata compatibility field, 50 focused checks also passed. The wheel
contains eight intents and 51 phrases; an isolated installation loaded the
pack and returned the correct identity. PostgreSQL was stopped after the demo.
