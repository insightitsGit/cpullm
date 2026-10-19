"""Publish the recorded audit; no application or database mutations."""
import hashlib
import json
from pathlib import Path
import shutil

ROOT=Path(__file__).resolve().parent
ART=Path('C:/Users/parva/.codex/visualizations/2026/10/16/01a1437c-705e-7ec3-a08d-7ac8707a6674')
NAMES=['audit-20261019-run1','audit-20261019-run2','audit-20261019-run3-current','audit-20261019-run4']

def main():
    datasets=[]
    for name in NAMES:
        source=ART/name
        dest=ROOT/name
        dest.mkdir(exist_ok=True)
        for file in ['protocol.json','source-sha256.json','runs.jsonl','summary.json','case-results.json','comparison.csv','benchmark.py','pytest-results.txt']:
            if (source/file).exists(): shutil.copy2(source/file,dest/file)
        datasets.append({'name':name,'summary':json.loads((source/'summary.json').read_text()),'cases':json.loads((source/'case-results.json').read_text()),'protocol':json.loads((source/'protocol.json').read_text())})
    a,b,c=[d['summary'] for d in datasets[:3]]
    latest=datasets[-1]['summary']
    before=json.loads((ART/NAMES[0]/'source-sha256.json').read_text())
    after=json.loads((ART/NAMES[2]/'source-sha256.json').read_text())
    changed=[k for k in sorted(set(before)|set(after)) if before.get(k)!=after.get(k)]
    (ROOT/'snapshot-changes.json').write_text(json.dumps(changed,indent=2))
    unit=ROOT/'audit-20261019-unit-current'
    unit.mkdir(exist_ok=True)
    for file in ['sha256.json','pytest-results.txt']:
        shutil.copy2(ART/'audit-20261019-unit-current'/file,unit/file)
    report=f'''# Executed audit: retrieval, displayed answers, and latency

Run date: 19 October 2026 UTC. **648 measured live calls, zero API exceptions**, across four frozen source/corpus configurations. Each configuration ran 27 questions three times through retrieval and three times through the full Appliance. No remote language model was used. These are hand-authored diagnostic cases, not a representative accuracy benchmark.

## What the evidence establishes

Retrieval found **all declared premises for 21/21 answerable questions** in every configuration. The gold fact was in the top five for all 17 factual questions. The live France question correctly returned Paris when the source explicitly stated that Paris is the capital of France. This audit does not support the earlier general claim that retrieval is broken.

The initial frozen source answered **15/17 factual questions**, **2/4 absent-fact questions with an explicit nonanswer**, **2/2 arithmetic questions**, and **1/4 policy questions under the source-only implication rubric**. The 217-paragraph run kept the same factual score but explicit nonanswers fell to **1/4**.

A concurrent answerability change was detected and retested as snapshot B. It narrowed capital answers to the requested country and explicitly declined the missing Spain fact. It also declined two supported diet questions that snapshot A answered. Snapshot B scored **13/17 factual answers, 3/4 absent-fact nonanswers, 2/2 arithmetic answers, and 1/4 policy answers**.

The final jointly frozen source/test version, snapshot C, scored **{latest['facts']['passed']}/17 factual answers, {latest['missing']['passed']}/4 absent-fact nonanswers, {latest['math']['passed']}/2 arithmetic answers, and {latest['rules']['passed']}/4 policy answers**. Its [individual outputs]({NAMES[-1]}/case-results.json) determine whether an earlier finding remains reproducible. These counts refer to distinct questions; repetitions are not additional accuracy samples. The four configurations are versioned observations, not independent experiments on one unchanged checkout.

## Comparison and timing

Open the companion comparison canvas beside the chat for the full table and a question-by-question inspector. Portable tables are also available as CSV:

- [Snapshot A, 17 paragraphs]({NAMES[0]}/comparison.csv)
- [Snapshot A, 217 paragraphs]({NAMES[1]}/comparison.csv)
- [Snapshot B, 17 paragraphs]({NAMES[2]}/comparison.csv)
- [Snapshot C, 17 paragraphs]({NAMES[3]}/comparison.csv)

Snapshot A, 17 paragraphs: retrieval median **{a['latency']['retrieval']['median_ms']:.1f} ms**, p95 **{a['latency']['retrieval']['p95_ms_nearest_rank']:.1f} ms**; full pipeline median **{a['latency']['pipeline']['median_ms']:.1f} ms**, p95 **{a['latency']['pipeline']['p95_ms_nearest_rank']:.1f} ms**.

Snapshot A, 217 paragraphs: retrieval median **{b['latency']['retrieval']['median_ms']:.1f} ms**, p95 **{b['latency']['retrieval']['p95_ms_nearest_rank']:.1f} ms**; full pipeline median **{b['latency']['pipeline']['median_ms']:.1f} ms**, p95 **{b['latency']['pipeline']['p95_ms_nearest_rank']:.1f} ms**.

Snapshot B, 17 paragraphs: retrieval median **{c['latency']['retrieval']['median_ms']:.1f} ms**, p95 **{c['latency']['retrieval']['p95_ms_nearest_rank']:.1f} ms**; full pipeline median **{c['latency']['pipeline']['median_ms']:.1f} ms**, p95 **{c['latency']['pipeline']['p95_ms_nearest_rank']:.1f} ms**.

Snapshot C, 17 paragraphs: retrieval median **{latest['latency']['retrieval']['median_ms']:.1f} ms**, p95 **{latest['latency']['retrieval']['p95_ms_nearest_rank']:.1f} ms**; full pipeline median **{latest['latency']['pipeline']['median_ms']:.1f} ms**, p95 **{latest['latency']['pipeline']['p95_ms_nearest_rank']:.1f} ms**.

Each latency distribution contains 81 serialized calls. Startup/ingestion/warmups are excluded. One warmup per method preceded measurement; method order alternates by repetition, with retrieval first for two repetitions and pipeline first for one. p95 is the nearest-rank percentile, not a confidence bound. These are in-process calls including query encoding; full pipeline also includes its graph, reasoners and reply construction. No HTTP overhead is measured. Developer activity was not suspended, so timing differences cannot be attributed solely to corpus growth.

Startup was {a['startup_seconds']:.2f}, {b['startup_seconds']:.2f}, and {c['startup_seconds']:.2f} seconds respectively. Total ingestion was {a['ingest_seconds']:.2f}, {b['ingest_seconds']:.2f}, and {c['ingest_seconds']:.2f} seconds. In particular, the 217-paragraph ingestion took about 80 seconds; profiling is needed before attributing that cost to an individual component. This is not a large-corpus scaling test.

## Reproduced findings and concrete handoff

1. **Resolved during the audit: transient diet-question regression in snapshot B.** In snapshot B, `What does the harbor kestrel eat?` and the equivalent heron question returned `The retrieved passages do not settle that.` The corresponding `eats small fish` passage was retrieved. Both were answered in snapshot A and are answered again in snapshot C. The final C run also preserves the missing-country nonanswer. This is not an open failure in the final tested source. Keep the two positive diet cases as regression guards alongside negative same-entity/different-relation cases when changing `answerability.py` and its reply/assembly hooks.

2. **P1: polarity of a rule question is not reflected in the verdict.** `Is business class forbidden from Boston to Paris?` returns `Yes. Business class is allowed ...` in snapshots A, B, and C. Sources contain an allowance for flights over six hours and an eight-hour flight. Inspect `fact_bridge.answer`/`_answer` and the question-to-rule matching; the answer plan must carry the asked modality, rather than returning whether an allowance fires. Acceptance: `allowed?` yields YES, `forbidden?` yields NO for this fixture, with coherent text and the same evidence.

3. **P1 under the declared source-only rubric: permission is strengthened into an exclusive rule.** The two-hour and six-hour questions receive NO and wording that adds `only`, though the stored rule says `allowed for flights over six hours`. `_opinion` maps a nonmatching allowed condition to NO; its NO rendering introduces `only for`. Suggested fix: encode whether a rule states sufficient, necessary, or exclusive conditions. A sufficient allowance alone leaves the other cases unknown. If the product intentionally uses a closed-world policy convention, document and expose it explicitly. Under that convention, those two cases would pass instead; the modality failure above remains. This rubric is stated in the pre-execution case expectations, not inferred from the observed result.

4. **P2: retrieved location evidence is not delivered.** Both nesting questions retrieve the right passage first but display a definition and diet instead. This persists in the final snapshot C. Inspect the ingest proposition extraction and realization selection: `realization_order` only emits IDs that have stored EIR propositions. Suggested fix: trace the nesting sentence through extraction and add a checked locative realization, or return a clearly labeled directly supporting quotation when that form is outside the realizer grammar. Acceptance: the kestrel reply says `coastal cliffs`, and the heron reply says `tall trees`, without exchanging their subjects.

5. **P2: unsupported attributes can still yield unrelated text.** Asking the kestrel's weight gives its definition/diet in all four runs; with distractors it also includes a lobster's weight. No kestrel weight was supplied. This is an answer-responsiveness gap under an answer-only contract, not evidence that a retriever missed a nonexistent fact or that the quoted lobster weight was fabricated. Suggested fix: extend the declared relation/attribute support contract, with an explicit nonanswer or labeled evidence-only response when the asked attribute is absent. Acceptance: no unlabeled bird definition or lobster weight as the answer to the kestrel-weight question.

6. **P2: corpus vocabulary can change routing through spelling normalization.** In snapshot A with 200 distractors, `What color was the banana John ate?` becomes `What colour was the banana John ate?`; `frame_result` is null, and the displayed output is John's apple sentence. Without distractors the original question yields a missing-color nonanswer. The recorded `typos` field establishes the rewrite; no banana fact was supplied. Suggested fix: normalize supported spelling variants consistently in classifier/frame parsing, and protect grammatical routing terms from corpus-dependent typo replacement. Acceptance: both `color` and `colour` retain event-role semantics and decline this nonexistent banana event under both corpora. Snapshots B and C have only been tested on the 17-paragraph corpus, so this larger-corpus case remains unverified there.

These are observed examples, not an exhaustive defect inventory. The existing `audit_passed`/`shine_ok` fields must be interpreted by their actual contracts; their presence does not by itself certify that the displayed reply answers the user's question. Reproducing a nonresponsive reply with those flags is not proof that those checkers malfunction under their narrower proposition/source checks.

## Regression tests actually run

Snapshot A: **63 passed, 1 skipped, 1 deselected**, covering frames, answering, construction realizer, finance, documents, ranking, and Model01. Snapshot C, with source and tests frozen together: **79 passed, 1 skipped, 1 deselected**, additionally covering answerability. See the [final test transcript](audit-20261019-unit-current/pytest-results.txt) and [source/test hashes](audit-20261019-unit-current/sha256.json). An intermediate attempt ran newer tests against snapshot B and produced four failures; that mismatched-version transcript is retained but is not used as the regression verdict. The optional trained-extractor case was skipped because no trained extractor checkpoint was available. The Model01 PostgreSQL round-trip test was deliberately deselected because it writes a shared fixed model ID. These are targeted tests, not a claim that the entire repository suite passed. Live database behavior was tested independently by all 648 measured calls in unique namespaces.

## Reproduction, source identity, and limits

Python 3.12.10; Windows 11 build 26200; Intel Core Ultra 9 275HX, 24 reported cores/logical processors; 68,137,205,760 bytes physical RAM. Installed metadata: cpu-llm 1.8.0, torch 2.9.1, transformers 4.51.3, sentence-transformers 5.1.2, numpy 2.4.6, psycopg 3.3.4. Retrieval uses the installed MPNet model cache and the packaged projection. Hugging Face offline mode was forced.

HEAD was `5737285ff49714f2b3ea6759b719135040745961`, **with uncommitted source changes**. This was not a benchmark of a clean 1.8.0 release. Snapshot A was frozen before execution; the 217-paragraph run reused exactly that source. Snapshot B froze later concurrent edits. Snapshot C froze source and the corresponding tests together after further concurrent edits, and supplied the final test and live-question runs. [A-to-B changed source files](snapshot-changes.json) and each run's SHA-256 manifest identify the differences. Frozen source integrity was checked after each benchmark run. The full source snapshots remain in the local artifact directory; the portable review folder includes the raw observations and manifests. This report makes claims about the identified snapshots, not subsequent checkout edits. No source fixes were made as part of this audit.

The exact corpus, expected answers, expected supporting IDs, timestamps, versions, namespaces and dirty status are in each `protocol.json`. The additional 200 passages are the first eligible 150–1500 character rows in the shipped WikiText validation parquet, excluding the fixture's named entities and missing-fact terms. This is a reproducible distractor test, not a sampled public QA dataset. All 17 controlled facts stay in the same `audit-notes` source, so title routing with many source documents has not been measured. There are no adversarial access-control, concurrency, security, training-quality or production-scale claims here.

For factual retrieval, a hit means the declared source sentence was returned; multi-premise recall requires every gold ID. Top-one factual evidence coverage was 14/17 in all configurations, and top-five was 17/17. Full-pipeline factual answer scoring checks fixture-specific subject/value phrases, followed by review of every unique displayed reply. The scorer is intentionally transparent and narrow: it is not a reusable semantic truth evaluator. Extra source-faithful sentences do not fail a correct factual answer in this rubric. Retrieval-only output is a passage list; no unsupported-question abstention or policy-reasoning ability is attributed to that baseline.

From the repository, with dependencies, cached encoder and the documented development PostgreSQL running:

```powershell
python docs/reviews/2026-10-19/benchmark.py --out C:/path/to/new-run
python docs/reviews/2026-10-19/analyze.py C:/path/to/new-run
python docs/reviews/2026-10-19/benchmark.py --out C:/path/to/new-larger-run --source-root C:/path/to/new-run/snapshot --distractors 200
python docs/reviews/2026-10-19/analyze.py C:/path/to/new-larger-run
```

Use new output directories. Each execution creates and retains its own unique namespace and local cache for inspection; it does not modify existing corpus documents. The run-specific saved `benchmark.py` records exactly which harness version produced that run; invoke the repository harness for new executions because it resolves the checkout relative to its location. Inspect every new reply before accepting the fixture scores. A future agent should use the 27 cases as regression checks and add independent held-out examples before making broader quality claims.
'''
    (ROOT/'audit.md').write_text(report,encoding='utf-8')
    blob=json.dumps([{k:d[k] for k in ['name','summary','cases']} for d in datasets],ensure_ascii=False)
    canvas='''import { Stack,H1,H2,Text,Table,Select,Callout,useHostTheme,useState } from "cursor/canvas";
const data = '''+blob+''';
const labels=["A · 17 paragraphs","A · 217 paragraphs","B · 17 paragraphs","C · 17 paragraphs (final tested source)"];
const ratio=(x:{passed:number,total:number})=>`${x.passed}/${x.total}`;
export default function Audit(){
 const t=useHostTheme();const [config,setConfig]=useState("3");const [key,setKey]=useState("bird_diet");
 const d=data[Number(config)];const row=d.cases.find(x=>x.id===key)||d.cases[0];
 return <Stack gap={22} style={{padding:24,maxWidth:1280,margin:"0 auto",background:t.bg.editor,color:t.text.primary}}>
 <Stack gap={6}><Text>Executed 19 October 2026 UTC · cpu-llm dirty checkout at 5737285</Text><H1>Retrieval succeeds; answer delivery has measurable gaps</H1><Text>648 measured live calls, zero API exceptions. 27 diagnostic questions × 3 repetitions × 2 methods × 4 configurations. Each run used a unique PostgreSQL namespace and a frozen source snapshot.</Text></Stack>
 <Callout>With an explicit France source, Paris is correctly returned. All declared premises were retrieved for 21/21 answerable questions in every configuration. This audit does not establish a general retrieval defect.</Callout>
 <H2>Comparison of source snapshots and corpus sizes</H2>
 <Table headers={["Measure",...labels]} rows={[
 ["Factual source retrieved in top 1 (17 cases)",...data.map(x=>ratio(x.summary.baseline_fact_gold_at1))],
 ["Factual source retrieved in top 5 (17 cases)",...data.map(x=>ratio(x.summary.baseline_fact_gold_at5))],
 ["All required premises in pipeline passages (21 cases)",...data.map(x=>ratio(x.summary.pipeline_all_premises_in_passages))],
 ["Displayed factual answers correct",...data.map(x=>ratio(x.summary.facts))],
 ["Explicit nonanswers when facts absent",...data.map(x=>ratio(x.summary.missing))],
 ["Policy answers correct under source-only rubric",...data.map(x=>ratio(x.summary.rules))],
 ["Arithmetic answers correct",...data.map(x=>ratio(x.summary.math))],
 ["Identical display across three repeats",...data.map(x=>`${x.summary.stable_display_cases}/27`)]
 ]}/>
 <Text>Counts are distinct questions, not independent repeated accuracy samples. This is a small hand-authored diagnostic set. Policy scoring treats “allowed if” as a sufficient condition, not an exclusive policy. Two additional policy cases would pass under an explicit closed-world convention. No external product is benchmarked.</Text>
 <H2>Observed warmed latency in milliseconds</H2>
 <Table headers={["Configuration","Retrieval median / p95 (ms)","Full pipeline median / p95 (ms)","Startup (s)","Ingest (s)"]} rows={data.map((x,i)=>[labels[i],`${x.summary.latency.retrieval.median_ms.toFixed(1)} / ${x.summary.latency.retrieval.p95_ms_nearest_rank.toFixed(1)}`,`${x.summary.latency.pipeline.median_ms.toFixed(1)} / ${x.summary.latency.pipeline.p95_ms_nearest_rank.toFixed(1)}`,x.summary.startup_seconds.toFixed(2),x.summary.ingest_seconds.toFixed(2)])}/>
 <Text>Source: saved runs.jsonl, 81 serialized calls per method/configuration. p95 uses nearest rank. Encoding is included; startup, ingestion and warmups are excluded. This machine was not reserved exclusively for benchmarking. CPU: Core Ultra 9 275HX; Python 3.12.10. Snapshots B and C were not tested with 217 paragraphs.</Text>
 <H2>Inspect every recorded answer</H2>
 <Select value={config} onChange={setConfig} options={labels.map((label,i)=>({value:String(i),label}))}/>
 <Select value={key} onChange={setKey} options={d.cases.map(x=>({value:x.id,label:x.question}))}/>
 <Stack gap={8}><Text><strong>Question:</strong> {row.question}</Text><Text><strong>Predeclared expectation:</strong> {row.expected}</Text><Text><strong>Retrieval-only first passage:</strong> {row.baseline_top1}</Text><Text><strong>Full pipeline displayed reply:</strong></Text><pre style={{whiteSpace:"pre-wrap",margin:0}}>{row.display_text}</pre><Text><strong>Repeated outcomes:</strong> {row.outcomes.join(" · ")}</Text><Text><strong>Gold evidence IDs:</strong> {row.gold_ids.join(", ")||"No stored answer declared"}</Text><Text><strong>Retrieved IDs:</strong> {row.baseline_ids.join(", ")}</Text><Text><strong>Recorded audit / Shine:</strong> {String(row.audit_passed)} / {String(row.shine_ok)}. These flags have narrower contracts than question-answer correctness.</Text></Stack>
 <H2>Fixes for the next agent</H2>
 <Table headers={["Priority","Observed issue","Fix and acceptance check"]} rows={[
 ["Resolved in C","Snapshot B declined supported bird diets","Both diets answer again in C, with Spain nonanswer preserved. Retain these regression cases."],
 ["P1","Forbidden? receives Yes, allowed","Carry the asked modality into the answer plan; allowed? YES, forbidden? NO on the same evidence."],
 ["P1, contract-dependent","Allowance becomes an exclusive prohibition","Represent sufficient vs necessary/exclusive conditions; unknown unless exclusivity is stated or configured."],
 ["P2","Nesting source retrieved first but not spoken","Trace locative extraction and realization; deliver coastal cliffs / tall trees for the correct bird."],
 ["P2","Unstated bird weight receives unrelated facts","Bind the requested attribute; explicit nonanswer or clearly labeled evidence-only output."],
 ["P2","Distractors change color to colour and bypass frame routing","Normalize spelling variants across typo correction and frame parsing; decline missing banana event with both spellings."]
 ]}/>
 <Text>Targeted tests: snapshot A 63 passed; final jointly frozen snapshot C 79 passed. Each had 1 skipped and 1 deselected. The skipped test requires an unavailable extractor checkpoint; the excluded test writes a fixed shared database model ID. See audit.md and raw transcripts for full reproduction details. No production code fixes were made in this audit.</Text>
 </Stack>;
}
'''
    target=Path('C:/Users/parva/.cursor/projects/c-code-cpullm/canvases/executed-audit-20261019.canvas.tsx')
    target.write_text(canvas,encoding='utf-8')
    print('Report:',ROOT/'audit.md')
    print('Canvas:',target)
    print('Source files changed between snapshots:',changed)

if __name__=='__main__': main()
