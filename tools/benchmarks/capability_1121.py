"""Live CrossDomain, invention, scan, and scale probes for the 1.12.1 wheel."""
import argparse
import hashlib
import importlib.metadata
import json
import os
import platform
from pathlib import Path
import statistics
import sys
import time
import uuid

import cpu_llm
from cpu_llm.constraint_evaluator import ObservableLimit, ParameterAxis, scan_constraints
from cpu_llm.documents import SourceDocument
from cpu_llm.pipeline import Appliance


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--out', type=Path, required=True)
    parser.add_argument('--wheel', type=Path, default=Path('dist/1.12.1/cpu_llm-1.12.1-py3-none-any.whl'))
    args = parser.parse_args()
    if not os.environ.get('VECTORPRISM_PG_DSN'):
        parser.error('Set VECTORPRISM_PG_DSN to a disposable pgvector database.')
    version = importlib.metadata.version('cpu-llm')
    if version != '1.12.1' or 'site-packages' not in Path(cpu_llm.__file__).parts:
        parser.error(f'Install the 1.12.1 wheel first. Found {version}.')
    wheel_sha256 = hashlib.sha256(args.wheel.read_bytes()).hexdigest()
    args.out.mkdir(parents=True, exist_ok=False)
    cases = []

    def record(case, prompt, result, expected, actual, seconds):
        cases.append(dict(case=case, prompt=prompt, expected=expected, actual=actual,
                          passed=expected == actual, seconds=seconds, response=result))
        (args.out / 'responses.json').write_text(json.dumps(cases, indent=2, default=str), encoding='utf-8')

    def ask(app, case, prompt, expected, actual, **kwargs):
        started = time.perf_counter()
        result = {}
        try:
            result = app.ask(prompt, **kwargs)
            observed = actual(result)
        except Exception as exc:
            observed = dict(error=f'{type(exc).__name__}: {exc}')
        record(case, prompt, result, expected, observed, time.perf_counter() - started)

    def interval(result):
        return next((join['outcome'] for join in result.get('invention', {}).get('joins', [])
                     if 'outcome' in join), result['status'])

    def claim(domain, common, **fields):
        return SourceDocument(domain, ('CrossDomain claim: ' + json.dumps(dict(common, **fields)),))

    def status(result):
        return result.get('status') or result.get('answer_status')
    common = dict(topic='Leptogenesis', quantity='effective Majorana mass',
                  conditions='illustrative normal-ordering slice', convention='benchmark',
                  interval_basis='diagnostic scenario')
    with Appliance(namespace='capability_' + uuid.uuid4().hex[:10], prompt_backend='rules') as app:
        app.ingest(SourceDocument('physics-rotation', (
            'The Casas-Ibarra matrix is complex orthogonal and satisfies R^T R = I.',)))
        prompt = 'CrossDomain: Casas-Ibarra.'
        ask(app, 'missing-math', prompt, 'insufficient_evidence', status)
        app.ingest(SourceDocument('math-rotation', (
            'For complex z, the rotation built from cos(z) and sin(z) is complex orthogonal and satisfies R^T R = I.',)))
        ask(app, 'orthogonality', prompt, [True, 2],
            lambda result: [result['invention']['check']['passed'], len(result['invention']['joins'][0]['premises'])])
        extras = ['algebra', 'numerics', 'methods', 'modeling', 'verification']
        for domain in extras:
            app.ingest(SourceDocument(domain + '-rotation', (
                'The rotation is complex orthogonal and satisfies R^T R = I.',)))
        ask(app, 'seven-kb', 'Research Casas-Ibarra using KBs: physics, math, ' + ', '.join(extras) + '.',
            7, lambda result: len(result['invention']['joins'][0]['premises']))
        app.ingest(claim('physics-slice', common, role='prediction', lower='6.31', upper='6.31', unit='meV'))
        app.ingest(claim('math-interval', common, role='method', operation='compare_intervals'))
        bound = 'Constraint Check: Leptogenesis using KBs: physics, math, experiment.'
        app.ingest(claim('experiment-limit', common, role='bound', upper='0.028', unit='eV'))
        ask(app, 'cross-unit-bound', bound, 'within_bound', interval)
        app.ingest(claim('experiment-limit', common, role='bound', upper='0.005', unit='eV'))
        ask(app, 'replace-bound', bound, 'outside_bound', interval)
        app.ingest(claim('experiment-limit', dict(common, convention='incompatible'),
                         role='bound', upper='0.028', unit='eV'))
        ask(app, 'incompatible-convention', bound, 'insufficient_evidence', interval)
        calibration = dict(common, topic='Calibration', quantity='length', conditions='room temperature',
                           convention='shared protocol', interval_basis='reported interval')
        app.ingest(claim('lab-calibration', calibration, role='measurement', lower='10', upper='12', unit='cm'))
        app.ingest(claim('field-calibration', calibration, role='measurement', lower='0.13', upper='0.14', unit='m'))
        ask(app, 'measurement-discrepancy', 'Constraint Check: Calibration using KBs: lab, field.',
            'disjoint_intervals', interval)
        app.ingest(SourceDocument('physics-mechanisms', (
            '| Model | Proposed Mechanism | Test | | --- | --- | --- | '
            '| Leptogenesis | Heavy neutrino decays create a lepton imbalance that processes convert into a baryon asymmetry ($B$). | Neutrinoless double-beta decay. |',)))
        invention = 'Invention: Leptogenesis.'
        session = dict(session_id='capability')
        def scan_summary(result):
            scan = result['invention']['proposals'][0]['constraint_scan']
            return [scan['sampled'], scan['accepted'], scan['brackets']]
        ask(app, 'automatic-scan', invention, [4000, 30, 140], scan_summary, **session)
        ask(app, 'invention-follow-up', 'Can you explain more?', True,
            lambda result: 'Lowest passing sampled point' in result['reply']['text'], **session)
        ask(app, 'invention-refinement', 'Go deeper.', True,
            lambda result: 'Bisection on a fixed slice' in result['reply']['text'], **session)
        app.ingest(SourceDocument('fixture-label', ('The color of Aster is blue.',)))
        timings = {}
        probe = 'What is the color of Aster?'
        for count in (0, 1000):
            ingest_started = time.perf_counter()
            if count:
                app.catalog_chunks([(f'scale-p{i:04d}', f'The archive shelf {i} is listed in the inventory.')
                                    for i in range(count)])
            ingest_seconds = time.perf_counter() - ingest_started
            samples = []
            for i in range(10):
                started = time.perf_counter()
                reply = app.ask(probe, strict_evidence=True)
                samples.append(time.perf_counter() - started)
                record(f'scale-{count}-{i}', probe, reply, 'evidence_quote', status(reply), samples[-1])
            timings[count] = dict(added_chunks=count, ingest_seconds=ingest_seconds,
                                  p50_seconds=statistics.median(samples), p95_seconds=max(samples))
    started = time.perf_counter()
    scan = scan_constraints('known intersection', lambda p: {'target': p['x'] + p['y'], 'lab': p['x']},
                            [ParameterAxis('x', '1', [0, 1, 2]), ParameterAxis('y', '1', [0, 1])],
                            {'target': '1', 'lab': '1'},
                            [ObservableLimit('target', 'target', '1', 'synthetic', lower=2, upper=2),
                             ObservableLimit('lab', 'lab', '1', 'synthetic', upper=1)])
    record('synthetic-scan', 'target = x+y and lab = x', scan, [1, 3],
           [scan['accepted_count'], len(scan['transition_brackets'])], time.perf_counter() - started)
    summary = dict(version=version, python=sys.version, platform=platform.platform(),
                   processor=platform.processor(), logical_cpus=os.cpu_count(),
                   wheel_sha256=wheel_sha256, installed_module=cpu_llm.__file__,
                   cases=len(cases), passed=sum(case['passed'] for case in cases),
                   failures=[case['case'] for case in cases if not case['passed']], timings=timings)
    (args.out / 'summary.json').write_text(json.dumps(summary, indent=2), encoding='utf-8')
    print(json.dumps(summary, indent=2))
    return int(bool(summary['failures']))


if __name__ == '__main__':
    raise SystemExit(main())
