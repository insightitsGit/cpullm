# Live tone-node chat examples

Executed November 2, 2026 through the public `Appliance.ask` API on runtime `271d685`.
The demonstration runner was captured by SHA-256 before execution. The Aster is a fictional
example object; the label is fictional test data, not medication guidance. No runtime code
was changed for this demonstration. PostgreSQL was stopped afterward.

Each turn below was run with and without its explicit style setting after resetting session
state. All eight canonical replies and canonical evidence sets were identical. These are
independent example turns, not proof of cross-turn memory. Tone is supplied by the application,
not inferred from the user prompt. Successful companions are paraphrases, not source quotes.

## 1. formal-color

API style: `"formal"`.

**User:** What color is the Aster?

**Response:**

> The color of the Aster is blue.

Style status: `generated`; alignment: `supported`.

## 2. friendly-location

API style: `"friendly"`.

**User:** Where does the Aster live?

**Response:**

> You can find the Aster in coastal waters.

Style status: `generated`; alignment: `supported`.

## 3. analytical-weight

API style: `"analytical"`.

**User:** What is the weight of the Aster?

**Response:**

> The weight of the Aster is 12.5 pounds.

Style status: `unchanged`; alignment: `supported`.

## 4. five-fact-composition

API style: `{"tone": "friendly", "max_sentences": 3, "clauses_per_sentence": 2}`.

**User:** Tell me the color, habitat, shape, material, and weight of the Aster.

**Response:**

> The Aster is blue, and you can find the Aster in coastal waters. The Aster has a round shape, and the Aster is made of steel. The Aster weighs 12.5 pounds.

Style status: `generated`; alignment: `supported`.

## 5. poetic-fallback

API style: `"poetic"`.

**User:** What color is the Aster?

**Response:**

> The color of the Aster is blue.

Style status: `generated`; alignment: `neutral_fallback`.
This is neutral factual wording, not successful poetic generation.

## 6. relationship-restriction

API style: `{"tone": "intimate", "relationship": 1}`.

**User:** What color is the Aster?

**Response:**

> From tone-chat-p0001:
> The Aster is blue.

Style status: `skipped`; alignment: `not applicable`.
Reason: `relationship_tone_conflict`.
No companion was published; the response shown is the unchanged canonical reply.

## 7. strict-label

API style: `"friendly"`.

**User:** What is the strength of Fictional DemoMed?

**Response:**

> Source quotations (not clinically validated):
> [tone-label-p0001] The strength of Fictional DemoMed is 0.75 mg.

Style status: `disabled`; alignment: `not applicable`.
Strict evidence mode bypassed style; this is the canonical labeled source quotation.

## 8. finance-boundary

API style: `"friendly"`.

**User:** Decide this LedgerCovenant test.  
threshold: 4.50  
numerator: compliance_certificate 9000001  
denominator: compliance_certificate 2000000  


**Response:**

> LedgerCovenant: BREACH. The computed value is 4.500001x and the test is lte 4.500000x. compliance_certificate is the only figure. Denominator: compliance_certificate is the only figure. This decision is the arithmetic and the precedence trace for the figures supplied. It is not legal advice and it does not declare a default.

Style status: `skipped`; alignment: `not applicable`.
Reason: `no_supported_immutable_frame`.
No companion was published; the response shown is the unchanged canonical reply.

## Reproduce and inspect

After the usual database/cached-model setup, run
`python tools/tone_chat_demo.py --out build/tone-chat-new-run` with a new output directory.
The runnable file is in `tools/`; the archived runner is a source snapshot.
`responses.json.gz` retains the full actual API results; `inputs.json`, `freeze.json`,
`summary.json` and `artifact-hashes.json` preserve inputs, provenance and checks.

The current style adapter covers color, location, shape, material and explicit weight.
It has ten reviewed constructions and ten tone controls, with limited expressive diction.
It does not style generic clinical attributes or finance verdicts. Strict mode disables it.
See [the specification](../../stylistic-generation-spec.md) and
[the consumer guide](../../library-consumer-guide.md).
