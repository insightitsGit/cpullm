"""Frontier -> Deepen on the saved AI-bottlenecks corpus, with holdouts restored.

Run from the repository root after preparing the optional workspace spaCy model.
Uses the existing disposable localhost database; no hosted-model calls.
"""
import hashlib
import json
import os
from pathlib import Path
import re
import subprocess
from time import perf_counter

from cpu_llm.documents import SourceDocument, chunks_for, open_source
from cpu_llm.pipeline import Appliance


def save(path, value):
    path.write_text(json.dumps(value, indent=2, ensure_ascii=False, default=str), encoding='utf8')


if __name__ == '__main__':
    root = Path.cwd()
    out = root / 'build/ai-bottlenecks-fixed-run'
    out.mkdir(parents=True, exist_ok=True)
    fixtures = root / 'tests/fixtures/ai_bottlenecks'
    restored = {}
    for block in re.split(r'^## ', (fixtures / 'holdout.md').read_text(encoding='utf8'), flags=re.M)[1:]:
        source = re.search(r'Source:\s*https://arxiv.org/abs/([\d.]+)', block)
        if source:
            restored[source[1]] = re.findall(r'^> (.+)$', block, re.M)
    chunks, manifest = [], []
    for path in sorted(fixtures.glob('arxiv-*.md')):
        document = open_source(path)[0]
        quotes = restored.get(path.stem.removeprefix('arxiv-'), [])
        document = SourceDocument(document.name, document.paragraphs + tuple(quotes), document.connections)
        parts = chunks_for(document)
        chunks.extend(parts)
        manifest.append(dict(file=str(path.relative_to(root)), sha256=hashlib.sha256(path.read_bytes()).hexdigest(),
                             chunks=len(parts), restored_passages=len(quotes)))
    model = root / 'build/ai-bottlenecks-nlp/en_core_web_sm/en_core_web_sm-3.8.0'
    if not model.exists():
        raise RuntimeError('Prepare the compatible spaCy model in the workspace first.')
    os.environ['FRONTIER_PARSER'] = str(model)
    revision = subprocess.check_output(['git', 'rev-parse', 'HEAD'], text=True).strip()
    metadata = dict(revision=revision, namespace='ai_bottlenecks_regression_a4cbb03',
                    documents=len(manifest), expected_chunks=len(chunks),
                    restored_passages=sum(len(v) for v in restored.values()), parser='en_core_web_sm-3.8.0',
                    holdouts_restored=True, manifest=manifest, runs=[],
                    caveat='A source gap or synthesized hypothesis is not proof of worldwide scientific novelty.')
    save(out / 'manifest.json', metadata)
    save(out / 'corpus.json', chunks)
    print(json.dumps({k: metadata[k] for k in ('documents', 'expected_chunks', 'restored_passages', 'parser')}), flush=True)
    os.chdir(out)
    with Appliance(namespace=metadata['namespace'], small_talk=False, prompt_backend='rules',
                   dsn='postgresql://postgres@127.0.0.1:55433/cpullm_inference_live') as app:
        rows, when = app.index.strict_source_rows(None)
        if {r['document_id']: r['chunk_text'] for r in rows} != dict(chunks):
            started = perf_counter()
            app.catalog_chunks(chunks, encoder_workers=2)
            metadata['ingest_seconds'] = perf_counter() - started
        rows, when = app.index.strict_source_rows(None)
        assert {r['document_id']: r['chunk_text'] for r in rows} == dict(chunks)
        metadata['chunks'], metadata['snapshot'] = len(rows), when
        print('INGESTED', len(rows), 'chunks; seconds', metadata.get('ingest_seconds', 0), flush=True)
        from cpu_llm.frontier import parser
        parser()  # record first model load separately from per-request graph work
        from cpu_llm.answerability import _sentences
        gaps = []
        cue = re.compile(r'\b(?:open (?:question|problem)|remains? unclear|not yet understood|future work|'
                         r'leave.{0,40}future|still (?:unknown|unclear))\b', re.I)
        for row in rows:
            for sentence in _sentences(row['chunk_text']):
                if cue.search(sentence) and sentence in row['chunk_text']:
                    gaps.append(dict(document_id=row['document_id'], quote=sentence))
        save(out / 'source-gap-statements.json', gaps)
        print('SOURCE GAP STATEMENTS', len(gaps), flush=True)
        prompts = [
            ('What unexplored connections exist around AI energy bottlenecks?', 'AI energy bottlenecks'),
            ('What unexplored connections exist around training data supply?', 'training data supply'),
            ('What unexplored connections exist around memory bandwidth bottlenecks?', 'memory bandwidth bottlenecks'),
        ]
        for number, (prompt, topic) in enumerate(prompts, 1):
            started = perf_counter()
            response = app.ask(prompt, as_of=when, session_id=f'open-{number}',
                               frontier={'topic': topic, 'limits': {'max_seconds': 120}, 'deepen_top': 5})
            # An explicit Frontier option is used only for the budget. Its topic
            # is supplied explicitly so the natural-language shell is not a topic.
            item = dict(prompt=prompt, frontier_seconds=perf_counter() - started, response=response)
            receipt = response.get('frontier') or {}
            print('FRONTIER', number, response['answer_status'], len(receipt.get('hypotheses', [])),
                  'incomplete', receipt.get('incomplete'), flush=True)
            save(out / f'frontier-{number}.json', item)
            if receipt.get('hypotheses'):
                started = perf_counter()
                deepen = app.ask('Deepen idea 1.', as_of=when, session_id=f'open-{number}')
                item['deepen_prompt'] = 'Deepen idea 1.'
                item['deepen_seconds'] = perf_counter() - started
                item['deepen_response'] = deepen
                print('DEEPEN', number, deepen['answer_status'], (deepen.get('deepen') or {}).get('verdict'), flush=True)
                print('TOP HYPOTHESIS', receipt['hypotheses'][0]['text'], flush=True)
                save(out / f'deepen-{number}.json', deepen)
            metadata['runs'].append(item)
            save(out / 'results.json', metadata)
        transcript = []
        for item in metadata['runs']:
            transcript.extend(['## Frontier prompt', item['prompt'], '## Frontier response', item['response']['reply']['text']])
            if 'deepen_response' in item:
                transcript.extend(['## Deepen prompt', item['deepen_prompt'], '## Deepen response',
                                   item['deepen_response']['reply']['text']])
        (out / 'responses.md').write_text('\n\n'.join(transcript), encoding='utf8')
        print('COMPLETE', len(metadata['runs']), 'Frontier/Deepen pairs', flush=True)
