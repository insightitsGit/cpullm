"""Reproducible synthetic smoke test; requires a configured pgvector database."""
import argparse
import json
import hashlib
import subprocess
from pathlib import Path
from time import perf_counter

from cpu_llm.access import CallerContext
from cpu_llm.pipeline import Appliance


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--dsn', default=None)
    parser.add_argument('--out', default='build/inference-expansion-smoke')
    args = parser.parse_args()
    repository = Path(__file__).resolve().parents[1]
    output = Path(args.out).resolve()
    output.mkdir(parents=True, exist_ok=True)
    results = []
    # Isolate appliance state as well as PostgreSQL namespace from user data.
    import os
    os.chdir(output)
    chunks = [('tax-p0001', 'The Kestrel is a cutter.'),
              ('tax-p0002', 'Every cutter is a vessel.'),
              ('tax-p0003', 'Every vessel requires a radio.'),
              ('parts-p0001', 'The pump is a physical part of the engine.'),
              ('parts-p0002', 'The engine is located in the dock.')]
    records = [
        ('dates-p0001', dict(kind='interval', start='2026-01-01', end='2026-01-31')),
        ('dates-p0002', dict(kind='interval', start='2026-01-31', end='2026-02-28')),
        ('research-p0001', dict(kind='observation', id='O1', description='A spectrum peak was observed.')),
        ('research-p0002', dict(kind='explanation', id='H1', description='Material effect.',
                               explains=['O1'], contradicts=[], test='Change the material.')),
        ('research-p0003', dict(kind='explanation', id='H2', description='Detector effect.',
                               explains=['O1'], contradicts=[], test='Change the detector.')),
        *[(f'trial-p{i:04}', dict(kind='bernoulli', observation_id=str(i), population='demo', success=i < 5))
          for i in range(10)],
    ]
    chunks.extend((identifier, json.dumps(dict(schema='inference-record-v1', **record)))
                  for identifier, record in records)
    with Appliance(namespace='inference_expansion_smoke', dsn=args.dsn,
                   prompt_backend='rules', small_talk=False) as app:
        app.catalog_chunks(chunks)

        def run(prompt, expected, **kwargs):
            started = perf_counter()
            result = app.ask(prompt, **kwargs)
            assert result['answer_status'] == expected, result
            results.append(dict(prompt=prompt, expected=expected, seconds=perf_counter()-started, response=result))
            print(expected, prompt, flush=True)
            return result

        run('Infer whether Kestrel requires a radio.', 'derived_inference')
        run('Infer whether pump is located in dock.', 'derived_inference')
        run('Temporal: sources: dates-p0001, dates-p0002', 'calculated')
        run('Estimate the trial rate.', 'statistical_estimate', inference=dict(
            mode='inductive', source_ids=[f'trial-p{i:04}' for i in range(10)]))
        run('Compare explanations.', 'hypotheses', inference=dict(
            mode='abductive', source_ids=['research-p0001', 'research-p0002', 'research-p0003']))
        research = app.ask('Research Kestrel')
        assert any(r['verdict'] == 'ENTAILED_BY_RULES' for r in research['research_inference']['receipts'])
        assert research['reply']['text'].count('Rule inference (') == 1
        results.append(dict(prompt='Research Kestrel', response=research))
        run('Temporal: sources: dates-p0001, dates-p0002', 'unsupported', strict_evidence=True)
        run('Infer whether Kestrel requires a radio.', 'insufficient_evidence', caller=CallerContext(
            tenant_id=app.tenant_id, caller_id='scoped', request_id='inference-smoke',
            allowed_sources=frozenset({'tax-p0001'})))
    payload = dict(schema='inference-expansion-smoke-v1', synthetic=True,
        baseline_revision=subprocess.check_output(['git', 'rev-parse', 'HEAD'], cwd=repository, text=True).strip(),
        source_hashes={name: hashlib.sha256((repository / name).read_bytes()).hexdigest() for name in (
            'src/cpu_llm/inference.py', 'src/cpu_llm/evidence_analysis.py', 'src/cpu_llm/pipeline.py',
            'src/cpu_llm/abductive_bridge.py', 'src/cpu_llm/invention.py', 'src/cpu_llm/nammade/execute.py',
            'src/cpu_llm/crossdomin.py', 'src/cpu_llm/classifier.py')}, case_count=len(results), results=results)
    (output / 'results.json').write_text(json.dumps(payload, indent=2, default=str), encoding='utf8')
    print(f'{len(results)} smoke cases passed', flush=True)


if __name__ == '__main__':
    main()
