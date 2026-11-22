"""Replay the fixed, ingested AI corpus without changing its source records."""
import json
import hashlib
import os
from pathlib import Path

from cpu_llm.access import CallerContext
from cpu_llm.pipeline import Appliance


def main():
    root = Path.cwd()
    source_files = ['src/cpu_llm/' + name + '.py' for name in
                    ('deepen', 'deepen_review', 'frontier', 'hypothesis_routes', 'pipeline')]
    source_hashes = {name: hashlib.sha256((root / name).read_bytes()).hexdigest() for name in source_files}
    old = root / 'build/ai-bottlenecks-fixed-run'
    focused = json.loads((old / 'focused.json').read_text(encoding='utf-8'))
    metadata = json.loads((old / 'results.json').read_text(encoding='utf-8'))
    out = root / 'build/deepen-strengthening-replay'
    out.mkdir(exist_ok=True)
    os.environ['FRONTIER_PARSER'] = str(root / 'build/ai-bottlenecks-nlp/en_core_web_sm/en_core_web_sm-3.8.0')
    os.chdir(out)
    with Appliance(namespace='ai_bottlenecks_regression_a4cbb03', small_talk=False, prompt_backend='rules',
                   dsn='postgresql://postgres@127.0.0.1:55433/cpullm_inference_live') as app:
        caller = CallerContext(tenant_id=app.tenant_id, caller_id='strengthening-replay', request_id='review',
            allowed_sources=frozenset('arxiv-' + s.replace('.', '-') + '-p' for s in focused['sources']))
        opts = dict(topic='inference energy and output quality', limits=dict(max_seconds=120))
        before = app.ask('Frontier: inference energy and output quality.', caller=caller, as_of=metadata['snapshot'],
                         frontier=dict(opts, deepen_top=0))
        after = app.ask('Frontier: inference energy and output quality.', caller=caller, as_of=metadata['snapshot'],
                        frontier=dict(opts, deepen_top=5), session_id='focused')
        comparable = lambda r: [(h['id'], h['text'], h['scores']) for h in r['frontier']['hypotheses']]
        assert comparable(before) == comparable(after), 'Annotations changed candidate breadth/ranking.'
        print('BREADTH', len(comparable(after)), 'unchanged', flush=True)
        top = after['frontier']['hypotheses'][0]
        deepen = app.ask('Review the leading proposal.', caller=caller, as_of=metadata['snapshot'],
                         session_id='focused', deepen=dict(hypothesis=top, novelty=True))
        followups = [app.ask('Go deeper.', caller=caller, as_of=metadata['snapshot'], session_id='focused') for _ in range(2)]
        memory_h = metadata['runs'][2]['response']['frontier']['hypotheses'][0]
        memory = app.ask('Review the memory proposal.', as_of=metadata['snapshot'], deepen=memory_h)
        result = dict(snapshot=metadata['snapshot'], focused_chunk_count=focused['chunk_count'],
                      corpus_chunk_count=metadata['chunks'], breadth_unchanged=True,
                      implementation_sha256=source_hashes,
                      without_checks=before, with_checks=after, deepen=deepen, followups=followups, memory=memory)
        (out / 'results.json').write_text(json.dumps(result, indent=2, ensure_ascii=False), encoding='utf-8')
        sections = ['# Fixed AI corpus: strengthened Deepen', '## Frontier', after['reply']['text'],
                    '## Deepen', deepen['reply']['text']]
        for i, response in enumerate(followups, 1):
            sections += [f'## Follow-up {i}: Go deeper', response['reply']['text']]
        sections += ['## Previously invalid memory-access bridge', memory['reply']['text']]
        (out / 'responses.md').write_text('\n\n'.join(sections), encoding='utf-8')
        assert source_hashes == {name: hashlib.sha256((root / name).read_bytes()).hexdigest() for name in source_files}
        print('TOP', top['text'], flush=True)
        for name, response in [('focused', deepen), ('memory', memory)]:
            receipt = response['deepen']
            print(name, receipt['verdict'], receipt['composition']['status'], receipt['test_plan']['readiness'], flush=True)
        print('FOLLOWUPS', [r['deepen']['progress']['focus']['id'] for r in followups], flush=True)


if __name__ == '__main__':
    main()
