# Design/implementation gap review

Reviewed runtime `273ab48` (same implementation as `3b8ab1e`). No runtime fixes were made during this review. The subsequent domain pilot supplied concrete end-to-end reproductions; planned features are separated from defects below.

## Actionable findings

### P1: self-contained finance requests are blocked by generic reference resolution

`src/cpu_llm/pipeline.py:685` invokes `self.references.prepare` before finance ownership is selected at line 744. All twelve fresh public `ask` requests in the domain pilot, including complete invoice/covenant fields, returned “Which entity do you mean? Please give its full name.” The ordinary product phrasing “Review this RefundProof finding” / “Decide this LedgerCovenant test” contains demonstratives that the reference layer treats as unresolved entities.

Calling `cpu_llm.finance.validate_message` on exactly the same prompt fields reaches the specialist and produces calculations or specific input refusals. Thus component success does not establish public-pipeline success. This is a routing/ownership defect, not evidence that arithmetic failed twelve times. The false clarification also affects the two intentionally invalid financial cases: users receive an entity question rather than the actual conflict/zero-denominator explanation.

Fix the request ownership boundary: recognize a named structured specialist payload before generic pronoun binding. Bind “this finding/test” to its supplied structured record, or let the specialist report missing fields. Do not globally disable reference checks whenever a finance keyword occurs; a definition question such as “What is RefundProof?” must remain a factual request. Preserve raw-prompt guard, caller/scope checks and explicit missing-information behavior. Add live tests through `Appliance.ask` for valid, incomplete and conflicting payloads, with default and explicitly selected finance modes.

### P2: public covenant rendering loses requested precision and obscures boundary decisions

`src/cpu_llm/finance/ledgercovenant.py:502` calls `format_ratio` with its default two decimal places (`src/cpu_llm/finance/money.py:79`). The pilot explicitly requests six decimal places. All three component ratio cases ignore that output precision; two retain the correct numeric value but not its requested format. The boundary case has internal `computed_scaled=4500001` (six-place value `4.500001`), yet displays:

> LedgerCovenant: BREACH. The computed value is 4.50x and the test is lte 4.50x.

The business verdict and internal scaled value are correct under the module's current policy, but the public text erases the deciding difference. Hidden structured fields must not substitute for visible numeric fidelity. A more expressive style node must not guess the missing digits or inherit an audit for altered numbers.

Define an explicit numerical presentation contract, including scale, rounding mode and threshold-critical precision. Preserve enough digits to explain the decision; surface a rounding note if display precision differs from decision precision. Tests must compare visible text with the exact internal value at boundaries, not merely find the verdict keyword. Future comparison datasets must state rounding policy to every model rather than require knowledge of this implementation's defaults.

## Additional confirmed limits, not newly discovered implementation defects

- The previous rules/spaCy scenario audit confirms a wrong-relation fallback for a conversational color request in rules mode. spaCy handles the tested wording correctly. A style abstention does not repair that canonical answer.
- Every new domain-pilot style invocation skipped: finance outputs use specialist contracts, and generic medication/clinical attributes are outside the five approved style relations. The current stylistic node therefore adds no domain-specific generation capability to these cases. New typed adapters and proof-preserving constructions are required before claiming otherwise.
- Duplicate corroborating proofs, non-ASCII forms, broad vocabulary, inherited multi-premise facts and expressive emotional/poetic diction remain documented capability gaps. They should not be disguised as successful generation by counting their skips as answers.
- The medication limit question was not evaluated: the frontend requested explicit Context/Questions formatting. This is an input/coverage limitation in the supplied form, not a wrong comparison or a clinical safety result.
- Current clinical positives retrieve an already recorded diagnosis. They do not establish diagnostic reasoning, treatment suitability or medical safety.

## Positive evidence and review limits

The existing live scenario audit passed 98 stylistic contract scenarios and 16 layout/session tests on the committed implementation. Additional synthetic fault probes of a raising generation function and an attempted frame-state replacement both produced a rejected style result while leaving the canonical input unchanged. No invariant bypass was reproduced by those probes; they are not a comprehensive adversarial security review.

This was an executing-agent code/result review, not an independent clinician, accountant, security auditor or second model. Runtime and earlier benchmark results were preserved. See the [domain pilot report](../../benchmarks/2026-11-02-domain-pilot/REPORT.md) for raw reproductions, strict scorer limits and deferred comparison status.
