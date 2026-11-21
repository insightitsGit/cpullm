"""Run from repository root; uses only the disposable localhost test database."""
import hashlib
import json
import os
from pathlib import Path

from cpu_llm.pipeline import Appliance


if __name__ == '__main__':
    root = Path.cwd()
    out = root / 'build/frontier-deepen-fixed-smoke'
    out.mkdir(parents=True, exist_ok=True)
    os.chdir(out)
    os.environ['FRONTIER_PARSER'] = 'regex'
    results = []
    with Appliance(namespace='frontier_deepen_review_fixed', small_talk=False, prompt_backend='rules',
                   dsn='postgresql://postgres@127.0.0.1:55433/cpullm_inference_live') as app:
        app.catalog_chunks([
            ('bandwidth-p0001', 'Memory bandwidth increases inference throughput.'),
            ('throughput-p0001', 'Inference throughput increases serving revenue.'),
            ('revenue-p0001', 'Serving revenue increases research funding.'),
        ])
        result = app.ask('Frontier: memory bandwidth research funding.', session_id='smoke',
                         frontier={'limits': {'max_path_edges': 3, 'min_results': 1}})
        assert result['frontier']['hypotheses']
        hypotheses = result['frontier']['hypotheses']
        number = next(i for i, h in enumerate(hypotheses, 1) if len(h['via']) == 2)
        assert len(hypotheses[number - 1]['check']['links']) == 3
        results.append(dict(case='frontier_three_edges', response=result))
        result = app.ask(f'Deepen idea {number}.', session_id='smoke')
        assert len(result['deepen']['links']) == 3 and result['deepen']['verdict'] == 'all_links_supported'
        results.append(dict(case='numbered_three_edges', response=result))
        result = app.ask('Deepen: Memory bandwidth may reduce research funding through inference throughput '
                         'and then serving revenue.')
        assert result['deepen']['direction_check']['status'] == 'contradicted'
        assert result['deepen']['verdict'] == 'contested'
        results.append(dict(case='opposite_direction', response=result))
        app.catalog_chunks([('negation-p0001', 'Memory bandwidth does not reduce inference throughput.')])
        result = app.ask('Deepen: Memory bandwidth may increase research funding through inference throughput '
                         'and then serving revenue.')
        assert result['deepen']['verdict'] == 'all_links_supported'
        assert result['deepen']['links'][0]['counter_count'] == 0
        results.append(dict(case='unrelated_negation', response=result))
        result = app.ask('Check this.', deepen=dict(pattern='chain', anchors=['memory bandwidth', 'funding'], via=[1]))
        assert result['answer_status'] == 'needs_clarification'
        results.append(dict(case='malformed_input', response=result))
        result = app.ask('Deepen idea 99.', session_id='smoke', strict_evidence=True)
        assert result['answer_status'] == 'unsupported'
        results.append(dict(case='strict_followup', response=result))
    payload = dict(baseline='ec71024', synthetic=True, cases=len(results), results=results,
                   source_hashes={name: hashlib.sha256((root / name).read_bytes()).hexdigest() for name in (
                       'src/cpu_llm/frontier.py', 'src/cpu_llm/deepen.py', 'src/cpu_llm/pipeline.py')})
    (out / 'results.json').write_text(json.dumps(payload, indent=2, ensure_ascii=False, default=str), encoding='utf8')
    print('6/6 database-backed node smoke cases passed.', flush=True)
