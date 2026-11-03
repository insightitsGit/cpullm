# Domain evidence and numeric-fidelity comparison: pilot design

Status: pilot specification, November 2, 2026. Hosted comparison is deferred at the user's request until a free-account key is available. No paid API calls are authorized. This is an evaluation of evidence handling and arithmetic, not a clinical validation or a presumption that CPU LLM wins.

Current follow-up: the user selected a **local deterministic baseline** and
explicitly left the hosted arm unrun. `tools/benchmarks/evidence_v2.py` freezes
fresh fictional evidence cases and compares the public strict API with an
independently implemented canonical whole-record lookup/Decimal calculator.
It checks visible values, literal proof offsets/hashes, expected task statuses,
answerable coverage and correct nonanswers. It does not import the production
strict parser or use gold answers inside the baseline. A limited baseline is
not a stand-in for a hosted LLM or a clinical comparator.

`tools/benchmarks/domain_pilot.py --database <new-disposable-name> --out <new-dir>`
replays the original 24 cases through ordinary public `ask`; original archived
results remain immutable. Both runners require committed runtime sources and
record their revision and dataset hashes before model execution. Do not alter
scoring/gold after a run without a separately versioned rerun. Clinical release
gates are defined in [healthcare acceptance](healthcare-evidence-acceptance.md).

The [CPU-only pilot results](benchmarks/2026-11-02-domain-pilot/REPORT.md) and [gap review](reviews/2026-11-02/design-implementation-gaps.md) are now saved. Public finance requests were blocked by reference resolution; direct finance-component probes exposed precision-display gaps. Preserve these failures when preparing the later comparison. Explicitly spell out rounding policy in its new frozen inputs.

## Questions and fair comparisons

Measure answerable-task success, numeric/value/unit fidelity, refusal on genuinely missing information, unsupported assertions, proof retention and latency separately. Always-refuse is not a winning strategy: supported coverage and answer correctness must be reported beside abstention. Score visible text independently from internal fields. Do not give CPU LLM credit for a hidden number missing from its public response.

Run the committed runtime with its ordinary public `Appliance.ask` entry point, then the same request with `style="friendly"`. Canonical and styled-companion results are separate observations, not independent answered cases. The style adapter currently supports five simple attribute relations; finance specialists and most medication/clinical attributes are outside its adapter set. A correct skip preserves canonical content but does not demonstrate domain generation.

The first dataset contains 24 authored cases: 12 finance, 8 synthetic medication-label/arithmetic cases and 4 clinical-record/missing-information cases. Freeze source documents, original requests, expected values and scorer before execution. Use independent Decimal arithmetic for finance gold. Keep answerable and unanswerable denominators explicit; include precision boundaries and conflicts rather than only easy demonstrations.

Finance covers four-decimal refunds, currency separation, source-authority precedence, covenant compliance/breach, equal-authority conflicts, zero denominators and rounding near a threshold. The supplied business policy must accompany a future hosted model; no hidden rule-engine knowledge should be required. A deterministic calculator baseline should be included in a larger comparison so ordinary arithmetic is not misrepresented as unique reasoning.

Medication data and clinical records are **fictional test fixtures, not dosing instructions or patient data**. Cases cover literal strength/ingredient/storage/interval/maximum values, multiplication from supplied numbers and label-limit verification. Clinical positives retrieve explicitly recorded diagnoses; they do not infer a diagnosis. Missing-record cases should abstain. Diagnostic accuracy requires a separate independently reviewed clinical study; this pilot cannot establish treatment safety or superiority at diagnosis.

Real labels motivate later source-backed cases: a product-specific limit must not be confused with a general ingredient warning, and qualifiers/units matter. Use a pinned label revision and expert-reviewed gold before evaluating actual medication decisions. References: [DailyMed label](https://www.dailymed.nlm.nih.gov/dailymed/drugInfo.cfm?setid=e817bc4a-43ef-4126-b903-aabd1390cd0c), [FDA acetaminophen information](https://www.fda.gov/drugs/safe-use-over-counter-pain-relievers-and-fever-reducers/acetaminophen). No medical facts from those references are substituted for the fictional fixtures.

## Planned hosted arm

The user selected a free hosted model and then deferred setup. Groq currently lists `qwen/qwen3.8-27b` in its [Free-plan limits](https://console.groq.com/docs/rate-limits). Its [quickstart](https://console.groq.com/docs/quickstart) requires an account API key. No suitable key or running local model was found, so no hosted or local-decoder comparison is fabricated.

When a free-account key is available, verify model availability again, record the exact returned model/version and keep the same frozen cases. Supply the same sources and explicit finance rules, disable external tools for a clearly labeled no-tool arm, use temperature zero and bounded completions, and obey free-tier limits. Stop at quota errors; never change to paid service. Add a tool-assisted LLM/calculator arm later rather than claiming all LLM systems drift numbers.

No claims such as “better than LLMs,” “verified medication safety” or “wins at diagnosis” are supported before comparative results and appropriate independent review exist. Preserve all failures and unsupported cases; do not tune the library/scorer after observing a result without a separately versioned rerun.
