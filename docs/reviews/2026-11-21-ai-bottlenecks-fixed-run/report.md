# AI-bottlenecks Frontier → Deepen run

Date: 2026-11-21. Revision: `a4cbb03`.
This is an exploratory integration run, not an accuracy score or a demonstrated
scientific discovery. No runtime implementation was changed during this run.

## Corpus and setup

- Ingested 64 saved papers/abstracts, yielding 1,054 chunks in isolated namespace
  `ai_bottlenecks_regression_a4cbb03` in the disposable PostgreSQL database.
- Restored 20 benchmark-withheld passages from the repository's holdout manifest,
  appended to their original source documents without modifying the fixture files.
  This avoids intentionally withheld known findings masquerading as open questions.
- Used the real encoder/ingestion path and the official spaCy English dependency
  model `en_core_web_sm` 3.8.0, loaded from a temporary workspace folder. The
  installed spaCy version was 3.8.14. No shared Python installation was changed.
- Model download: [official release](https://github.com/explosion/spacy-models/releases/tag/en_core_web_sm-3.8.0).
  Wheel SHA-256: `1932429db727d4bff3deed6b34cfc05df17794f4a52eeb26cf8928f7c1a0fb85`.
- Frontier budget: 120 seconds, unchanged candidate/path/result limits, five
  leading Deepen checks. Each standalone Deepen examined the first returned item.
- The corpus contains both body text and abstract-only sources. Restoring known
  benchmark holdouts does not make it a complete or current scientific literature KB.

Ingestion took 176.5 seconds. All four completed Frontier searches reported
complete candidate searches, and no run exhausted its configured budget.

## Broad-domain results

1. Prompt: `What unexplored connections exist around AI energy bottlenecks?`
   Generated 252 candidates; 66 survived; returned 50. Frontier 15.04 s,
   standalone Deepen 3.92 s. First output:
   > matrix vector products may constrain AI applications through compute.

2. Prompt: `What unexplored connections exist around training data supply?`
   Generated 482 candidates; 60 survived; returned 50. Frontier 4.20 s,
   standalone Deepen 3.02 s. First output:
   > large investments may constrain substantial boost through Training.

3. Prompt: `What unexplored connections exist around memory bandwidth bottlenecks?`
   Generated 45 candidates; 7 survived; returned all 7, correctly reporting a
   shortage rather than padding the list. Frontier 4.02 s, Deepen 2.96 s.
   First output:
   > chunked prefill may increase divergence through memory access for prefill jobs (read as access).

All three first items received `all_links_supported`. This does not make them
good hypotheses: the memory example joins hardware memory transactions to social
access to compute resources, and the training example has no operationally defined
outcome beyond “substantial boost.” Exact citations and link checks alone did not
prevent these conceptual errors. Some candidates also contain malformed fragments.

## Focused follow-up

Restricted the same snapshot to the original corpus's energy and memory groups:
25 sources, 360 chunks. Used canonical `-p` source prefixes through CallerContext.
The first harness attempt used document slugs instead of source prefixes and
correctly received zero permitted chunks; the corrected run is the result below.

Exact prompt:
> What unexplored connections exist around inference energy and output quality?

Frontier generated 59 candidates; 7 survived; all 7 were returned with a shortage
notice. First output:
> implementation of H2O and vLLM may jointly drive throughput, and their effects may compound.

Exact follow-up: `Deepen idea 1.`

Deepen reported `all_links_supported`, with one cited support for H2O improving
throughput and two supports for vLLM improving throughput. Its directional
assessment was `unspecified`, not empirical validation of a joint effect.

Its proposed factorial experiment was:
> Run all four combinations of low and high implementation of H2O and vLLM; measure throughput.
> Hold grained batching mechanisms, latency, scattered reads fixed or record them as covariates.
> Compare the joint effect with the sum of the separate effects.

This is more concrete than the broad-domain outputs, but it still requires
operationalizing software configurations as interventions, selecting measurements
and verifying implementation compatibility. It tests throughput, not the requested
energy/output-quality trade-off. No combined implementation or experiment was run.

## Independent novelty check, after engine execution

The proposed generic H2O/vLLM connection is not a confirmed unanswered problem.
The vLLM project already received an H2O integration request in March 2024:
[issue #3532](https://github.com/vllm-project/vllm/issues/3532).
The August 2026 [vToken preprint](https://arxiv.org/abs/2608.13263) explicitly
describes implementation in vLLM and evaluation using H2O among its policies.
That does not validate every proposed interaction or workload, but it defeats
any claim that simply connecting H2O with vLLM is a new discovery.

These newer external sources were checked after the run and were not ingested
or supplied to the engine. They demonstrate a novelty-verification gap rather
than a change to the recorded test corpus.

## Source-stated gaps versus actual open problems

The source scan found 20 sentences with open-question/future-work markers; some
are headings or vague references and are not independently defined questions.
One useful source-stated research direction was the joint evaluation of inference
energy/performance while controlling decoding settings, output quality, workload
complexity, quantization and batching (arXiv 2310.03003). This was described as
future work by that paper, not established as unanswered worldwide today.

The run found candidate research directions and proposed tests. It did **not**
establish a genuinely novel, currently unsolved scientific question or solve one.

## Lessons for further improvements

- Check bridge identity using domain/semantic role, not head nouns and embedding
  proximity alone. Hardware memory access and institutional compute access differ.
- Preserve quantifiers and scope: a source saying not every application requires
  vast compute is not an unqualified universal bottleneck premise.
- Require operationally defined variables/outcomes; fragments such as “substantial
  boost,” “intra / inter -,” or publication markup cannot be experimental variables.
- Treat individual link support separately from support for composition, interaction,
  scientific usefulness, topical coverage and literature novelty.
- Add an explicit novelty-review step against current literature when claiming a
  new research direction, and keep its retrieval separate from initial generation.

## Artifacts and reproduction

Scripts: [full run](run.py), [focused scope](focused.py).
Local raw artifacts are under `build/ai-bottlenecks-fixed-run/`:
`results.json`, `focused.json`, `responses.md`, `focused-responses.md`,
`source-gap-statements.json`, `manifest.json` and `corpus.json`.
The full responses are preserved, including weak results and the invalid-scope
harness attempt; this report does not select a polished response as a pass score.
