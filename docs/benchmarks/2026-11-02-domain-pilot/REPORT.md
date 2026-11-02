# Domain pilot: evidence and numeric fidelity

Tested November 2, 2026 against fixed revision **`273ab480b8aa1d019f238b346081dfcb2a9ea844`**. The hosted model comparison was deferred by the user because no free-account API key was available. **No hosted calls or charges occurred. No comparative superiority result exists.**

The corpus and expected values were frozen before execution. There are 24 cases: 12 finance, 8 fictional medication-label/arithmetic cases and 4 fictional clinical-record cases. Every case ran through the public `Appliance.ask` boundary, then through the same boundary with `style="friendly"`: 48 live requests. All source documents and case/patient/product names are fictional benchmark fixtures, not clinical instructions or actual patient data.

## Public pipeline results

- **Finance: 0/12 strict cases passed.** All twelve were stopped before the finance node by “Which entity do you mean? Please give its full name.” Complete prompts such as “Review this RefundProof finding” and “Decide this LedgerCovenant test” were intercepted by reference resolution. The 0/12 result measures failure to route the supplied requests; it is not twelve arithmetic errors.
- **Medication fixture tasks: 7/8 passed.** Five supplied attribute lookups preserved their values/units and source IDs, and two explicit multiplications were correct. The remaining label-limit question received a request to format background as Context and requests as Questions. It was not processed as a limit comparison. These results are not medicine-verification accuracy on real labels.
- **Clinical-record fixtures: 4/4 passed.** Two cases retrieved explicitly recorded fictional diagnoses; two missing-information requests abstained. No diagnosis was inferred or clinically validated. Do not call this “100% diagnostic accuracy.”
- **Stylistic generation: skipped on all 24 cases.** The adapter does not support finance specialist contracts or these generic clinical/medication attributes. Canonical visible replies and evidence remained unchanged between ordinary and styled requests. This shows conservative behavior, not an added medical/financial wording capability.

Answerability denominators are saved separately in `summary.json`. Refusing an answerable task is not counted as a successful answer. Missing clinical evidence is not filled in to make the result look useful.

## Separate specialist component probe

To locate the finance failure, the exact twelve original finance prompts were also passed to `cpu_llm.finance.validate_message`, independently of `Appliance.ask`. This is explicitly a **component probe**, not a replacement for the failed end-to-end results.

The component passed **9/12 strict cases**:

- All six four-decimal refund examples preserved the expected recoverable amount and unverified/actionable distinction. The separate currency case preserved USD and EUR totals independently.
- Equal-authority conflicting facts and zero denominator inputs produced specific refusals rather than an invented ratio.
- All three ratio verdicts were correct. However, all three failed the explicit six-decimal display requirement. Two printed values were numerically equal to gold but lacked requested precision. The boundary case lost a material numeric difference in the visible text.

For the boundary case, the internal six-place value is `4.500001`, with verdict BREACH. Its public component text says:

> The computed value is 4.50x and the test is lte 4.50x.

That is a real presentation gap: the hidden computation retains the difference, but the reader cannot see why a breach was reported. Correct hidden numbers do not earn visible numeric-fidelity credit. See `finance-component.json` and the [gap review](../../reviews/2026-11-02/design-implementation-gaps.md).

## Scoring and dataset limitations

The pilot uses independent Decimal gold and strict visible-text checks. It is intentionally small, synthetic and aligned to named specialist input schemas. It is not an independent industry benchmark or a general semantic judge. The ratio gold uses six-place ROUND_HALF_UP; although the prompt explicitly asks for six decimals, the rounding mode is not fully spelled out in the original prompt. Before a hosted comparison, create a separately versioned dataset that explicitly supplies that policy or uses unambiguous rounding cases. Do not reuse this omission to label another model's valid rounding choice as drift.

Refund/currency checks expect the named business concepts in the visible response; they are not a universal natural-language scorer. A later hosted arm needs a declared response schema or independently reviewed semantic scoring. The finance policy text is saved for fair future prompting; no hidden specialist policy should be required of another model. A tool-assisted LLM/calculator arm should accompany a no-tool comparison.

The source-grounded medication questions simply ask about fictional supplied fields such as `375 mg`, a storage range, and a stated interval. The arithmetic questions are multiplication, not recommendations about safe doses. Clinical-record retrieval and missing-data refusal cannot validate diagnosis or treatment. A real healthcare evaluation requires authoritative pinned labels, appropriate case data, expert-reviewed expectations and a distinct safety protocol.

## What this establishes

There is promising component-level evidence for exact refund arithmetic, currency separation and explicit fact copying. The public finance routing gap and the ratio display issue must be addressed before marketing an end-to-end advantage. The current style adapter has no demonstrated domain-generation benefit on this dataset. No claim that CPU LLM beats hosted models, prevents all numerical drift, verifies actual medication safety or wins at diagnosis is justified by this pilot.

## Saved evidence and next comparison

`cases.json`, `sources.json`, `freeze.json`, `responses.jsonl.gz` and `summary.json` preserve the original public run. `finance-component.json` preserves the separate component probe. `runner-source.py` matches the frozen evaluator hash. `comparison-status.json` records zero API calls/spend and no hosted scores. Source changes were not made to improve this run.

The [benchmark design](../../domain-comparison-benchmark-design.md) records the planned free-hosted comparison and its limits. When a free-account key is available, verify model eligibility, freeze a new fully specified comparison dataset, provide the same evidence/rules, record model and sampling settings, and publish all failures. Do not relabel this CPU-only pilot as a comparison.
