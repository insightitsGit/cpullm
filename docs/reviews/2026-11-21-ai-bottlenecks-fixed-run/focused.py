"""Scope the already ingested corpus to its original energy/memory source groups."""
import ast
import hashlib
import json
import os
from pathlib import Path
from time import perf_counter

from cpu_llm.access import CallerContext
from cpu_llm.pipeline import Appliance


if __name__ == '__main__':
    root = Path.cwd()
    out = root / 'build/ai-bottlenecks-fixed-run'
    fixture_builder = root / 'docs/reviews/2026-11-21-frontier/scripts/build.py'
    tree = ast.parse(fixture_builder.read_text(encoding='utf8'))
    groups = next(ast.literal_eval(node.value) for node in tree.body if isinstance(node, ast.Assign)
                  and any(isinstance(t, ast.Name) and t.id == 'SUB' for t in node.targets))
    sources = sorted(set(groups['energy and power'] + groups['memory bandwidth']))
    prefixes = frozenset('arxiv-' + source.replace('.', '-') + '-p' for source in sources)
    os.environ['FRONTIER_PARSER'] = str(root / 'build/ai-bottlenecks-nlp/en_core_web_sm/en_core_web_sm-3.8.0')
    snapshot = json.loads((out / 'results.json').read_text(encoding='utf8'))['snapshot']
    os.chdir(out)
    with Appliance(namespace='ai_bottlenecks_regression_a4cbb03', small_talk=False, prompt_backend='rules',
                   dsn='postgresql://postgres@127.0.0.1:55433/cpullm_inference_live') as app:
        caller = CallerContext(tenant_id=app.tenant_id, caller_id='scoped-energy-memory',
                               request_id='open-question-focused', allowed_sources=prefixes)
        rows, _ = app.index.strict_source_rows(prefixes, as_of=snapshot)
        prompt = 'What unexplored connections exist around inference energy and output quality?'
        started = perf_counter()
        response = app.ask(prompt, caller=caller, as_of=snapshot, session_id='focused', frontier={
            'topic': 'inference energy and output quality', 'limits': {'max_seconds': 120}})
        elapsed = perf_counter() - started
        receipt = response.get('frontier') or {}
        print('SCOPED', len(sources), 'papers', len(rows), 'chunks', response['answer_status'],
              len(receipt.get('hypotheses', [])), 'incomplete', receipt.get('incomplete'), flush=True)
        result = dict(prompt=prompt, sources=sources, chunk_count=len(rows), seconds=elapsed, response=response,
                      scope_reason='Original corpus energy/memory groups; avoids joining hardware access to institutional access.')
        if receipt.get('hypotheses'):
            deepen = app.ask('Deepen idea 1.', caller=caller, as_of=snapshot, session_id='focused')
            result.update(deepen_prompt='Deepen idea 1.', deepen_response=deepen)
            print('TOP', receipt['hypotheses'][0]['text'], flush=True)
            print('DEEPEN', deepen['answer_status'], deepen.get('deepen', {}).get('verdict'), flush=True)
        (out / 'focused.json').write_text(json.dumps(result, indent=2, ensure_ascii=False, default=str), encoding='utf8')
        sections = ['## Focused Frontier prompt', prompt, '## Frontier response', response['reply']['text']]
        if 'deepen_response' in result:
            sections.extend(['## Deepen prompt', 'Deepen idea 1.', '## Deepen response',
                             result['deepen_response']['reply']['text']])
        (out / 'focused-responses.md').write_text('\n\n'.join(sections), encoding='utf8')
