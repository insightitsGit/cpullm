"""Frozen synthetic evidence acceptance + independent literal/calculator baseline.

No hosted calls, no real patient data, no clinical efficacy claim.
"""
from __future__ import annotations
import argparse
from decimal import Decimal, localcontext
import hashlib
import json
import os
from pathlib import Path
import re
import subprocess
import sys
import time

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / 'src'))


def write(path, value):
    path.write_text(json.dumps(value, indent=2, default=str) + '\n', encoding='utf-8')


def cases():
    data = []
    def add(id, sources, query, status, value=None, task_statuses=None):
        data.append(dict(id=id, sources=sources, query=query, status=status, value=value,
                         task_statuses=task_statuses, answerable=status in {'evidence_quote', 'derived_calculation', 'partial', 'completed'}))
    for i, (attribute, value) in enumerate([('strength', '0.625 mg'), ('ingredient', 'compound Z'),
        ('storage', 'cold'), ('recorded diagnosis', 'condition V'), ('recorded allergy', 'compound P'),
        ('expiry', '2030-01-01'), ('dose interval', '12 hours'), ('batch', 'B-0017')]):
        add(f'direct-{i}', [f'The {attribute} of Fictional Neral is {value}.'],
            f'What is the {attribute} of Fictional Neral?', 'evidence_quote', value)
    for i, source in enumerate(["Fictional Neral's strength is 0.625 mg.",
        'Fictional Neral has a strength of 0.625 mg.', 'The strength for Fictional Neral is 0.625 mg.']):
        add(f'paraphrase-{i}', [source], 'What is the strength of Fictional Neral?', 'evidence_quote', '0.625 mg')
    for i, (value, status) in enumerate([('0.125 mg', 'conflicting'), ('0.625 mL', 'conflicting'),
        ('not 0.625 mg', 'conflicting'), ('unknown', 'insufficient_evidence'),
        ('0.625 mg if condition X applies', 'insufficient_evidence'),
        ('0.000625 g', 'evidence_quote'), ('625 mcg', 'evidence_quote')]):
        add(f'conflict-equivalence-{i}', ['The strength of Fictional Neral is 0.625 mg.',
            f"Fictional Neral's strength is {value}."], 'What is the strength of Fictional Neral?', status,
            '0.625 mg' if status == 'evidence_quote' else None)
    for attribute in ('diagnosis', 'recommended treatment', 'interaction', 'safe dose'):
        add('missing-' + attribute, ['The symptom of Case Cedar is cough.'],
            f'What is the {attribute} of Case Cedar?', 'insufficient_evidence')
    for i, query in enumerate(['Which antibiotic should Case Cedar receive?', 'Can I take Fictional Neral?',
        'What is the strength of it?', 'What is the strength of Fictional Neral if pregnant?',
        'What is the strength of Fictional Neral or OtherMed?']):
        add(f'unsupported-{i}', ['The strength of Fictional Neral is 0.625 mg.'], query, 'unsupported')
    for i, (expression, value) in enumerate([('0.1 + 0.2', '0.3'), ('19 * 0.125', '2.375'),
        ('8 - 11', '-3'), ('999999.000001 * 2', '1999998.000002')]):
        add(f'arithmetic-{i}', [], 'Calculate ' + expression + '.', 'derived_calculation', value)
    add('source-calculation', ['The strength of Fictional Neral is 0.625 mg.'],
        'Calculate the strength of Fictional Neral times 4.', 'derived_calculation', '2.500 mg')
    add('source-calculation-conflict', ['The strength of Fictional Neral is 0.625 mg.',
        "Fictional Neral's strength is 1 mg."], 'Calculate the strength of Fictional Neral times 4.', 'conflicting')
    add('batch-reference', ['The strength of Fictional Neral is 0.625 mg.', 'The storage of Fictional Neral is cold.'],
        'What is the strength of Fictional Neral? What is the storage of it?', 'evidence_quote',
        task_statuses=['evidence_quote', 'evidence_quote'])
    add('field-list', ['The strength of Fictional Neral is 0.625 mg.', 'The storage of Fictional Neral is cold.'],
        'What are the strength and storage of Fictional Neral?', 'evidence_quote', task_statuses=['evidence_quote'] * 2)
    add('batch-partial', ['The strength of Fictional Neral is 0.625 mg.'],
        'What is the strength of Fictional Neral? What is the storage of it?', 'partial',
        task_statuses=['evidence_quote', 'insufficient_evidence'])
    add('batch-ambiguous', ['The strength of Fictional Neral is 0.625 mg.'],
        'What is the strength of Fictional Neral? What is the storage of OtherMed? What is the strength of it?',
        'partial', task_statuses=['evidence_quote', 'insufficient_evidence', 'unsupported'])
    add('join', ['Teral is a crustacean.', 'Every crustacean has a lifespan of 23 years.'],
        'What is the lifespan of Teral?', 'evidence_quote', '23 years')
    add('join-average-refusal', ['Teral is a crustacean.', 'The average lifespan of crustacean is 23 years.'],
        'What is the lifespan of Teral?', 'insufficient_evidence')
    add('join-conflict', ['Teral is a crustacean.', 'Every crustacean has a lifespan of 23 years.',
        'The lifespan of Teral is 19 years.'], 'What is the lifespan of Teral?', 'conflicting')
    overview = [f'The {attribute} of Fictional Neral is {value}.' for attribute, value in
                [('strength', '0.625 mg'), ('storage', 'cold'), ('ingredient', 'compound Z'), ('batch', 'B-0017')]]
    add('long-evidence-overview', overview, 'List documented attributes of Fictional Neral.', 'evidence_quote',
        task_statuses=['evidence_quote'] * 4)
    add('multisentence-qualifier-refusal', ['The strength of Fictional Neral is 0.625 mg. Another condition applies.'],
        'What is the strength of Fictional Neral?', 'insufficient_evidence')
    return data


def baseline(case, rows):
    """Independent canonical whole-record lookup and Decimal calculator.

    Deliberately has no aliases, joins, batch planner, or clinical reasoning.
    No production modules or gold answers are consulted.
    """
    query = case['query']
    calculation = re.fullmatch(r'Calculate ([+-]?\d+(?:\.\d+)?) ([+*\-]) ([+-]?\d+(?:\.\d+)?)\.', query)
    if calculation:
        with localcontext() as context:
            context.prec = 100
            a, b = Decimal(calculation[1]), Decimal(calculation[3])
            value = a + b if calculation[2] == '+' else a - b if calculation[2] == '-' else a * b
        return dict(answer_status='derived_calculation', calculation=dict(display=format(value, 'f')), answer_evidence=[])
    match = re.fullmatch(r'What is the (.+?) of (.+?)\?', query)
    if not match or re.search(r'\b(?:it|if|or)\b', match[2]):
        return dict(answer_status='unsupported', answer_evidence=[])
    pattern = re.compile(r'The ' + re.escape(match[1]) + ' of ' + re.escape(match[2]) + r' is ([^!?\n]+)\.')
    found = [(row, pattern.fullmatch(row['chunk_text'])) for row in rows]
    found = [(row, m[1]) for row, m in found if m and not re.search(r'(?<!\d)\.|\.(?!\d)', m[1])]
    status = 'insufficient_evidence' if not found else 'conflicting' if len({v for _, v in found}) > 1 else 'evidence_quote'
    evidence = [dict(document_id=r['document_id'], quote=r['chunk_text'], start=0, end=len(r['chunk_text']),
                     chunk_sha256=hashlib.sha256(r['chunk_text'].encode()).hexdigest()) for r, _ in found]
    return dict(answer_status=status, answer_evidence=evidence, reply=dict(text='\n'.join(p['quote'] for p in evidence)))


def score(case, result, rows):
    checks = dict(status=result.get('answer_status') == case['status'])
    if case.get('task_statuses'):
        checks['tasks'] = [t['status'] for t in result.get('task_results', [])] == case['task_statuses']
    evidence = result.get('answer_evidence') or []
    lookup = {r['document_id']: r['chunk_text'] for r in rows}
    checks['proof_integrity'] = all(p['document_id'] in lookup and
        lookup[p['document_id']][p['start']:p['end']] == p['quote'] and
        hashlib.sha256(lookup[p['document_id']].encode()).hexdigest() == p['chunk_sha256'] for p in evidence)
    if case['status'] == 'evidence_quote' or case['status'] == 'partial':
        checks['proof_present'] = bool(evidence)
        checks['proof_displayed'] = all(p['quote'] in (result.get('reply') or {}).get('text', '') for p in evidence)
    if case['value'] is not None:
        if case['status'] == 'derived_calculation':
            checks['exact_visible_value'] = (result.get('calculation') or {}).get('display') == case['value']
        else:
            checks['exact_visible_value'] = case['value'] in (result.get('reply') or {}).get('text', '')
    return dict(ok=all(checks.values()), checks=checks)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--out', type=Path, required=True)
    args = parser.parse_args()
    out = args.out.resolve()
    out.mkdir(parents=True, exist_ok=False)
    if subprocess.call(['git', 'diff', '--quiet', '--', 'src/cpu_llm'], cwd=ROOT):
        raise SystemExit('Commit runtime before benchmark execution')
    revision = subprocess.check_output(['git', 'rev-parse', 'HEAD'], cwd=ROOT, text=True).strip()
    dataset = cases()
    write(out / 'cases.json', dataset)
    write(out / 'freeze.json', dict(revision=revision, cases_sha256=hashlib.sha256((out / 'cases.json').read_bytes()).hexdigest(),
        runner_sha256=hashlib.sha256(Path(__file__).read_bytes()).hexdigest(), hosted='unrun_by_user_choice',
        clinical_validation=False, baseline='independent canonical whole-record lookup + Decimal calculator'))
    from cpu_llm.pipeline import Appliance
    from cpu_llm.access import CallerContext
    results = []
    with Appliance(namespace='evidence_bench_' + str(int(time.time())), prompt_backend='rules') as app:
        for i, case in enumerate(dataset):
            prefix = f'evidence-{i}-p'
            rows = [dict(document_id=f'{prefix}{j:04d}', chunk_text=text) for j, text in enumerate(case['sources'], 1)]
            app.index_chunks([(r['document_id'], r['chunk_text']) for r in rows])
            caller = CallerContext.make(app.tenant_id, 'benchmark', [prefix])
            start = time.perf_counter()
            response = app.ask(case['query'], strict_evidence=True, caller=caller)
            latency = time.perf_counter() - start
            plain = baseline(case, rows)
            verdict, plain_verdict = score(case, response, rows), score(case, plain, rows)
            results.append(dict(id=case['id'], strict=response, baseline=plain, strict_score=verdict,
                                baseline_score=plain_verdict, strict_seconds=latency))
            print(case['id'], verdict['ok'], flush=True)
    write(out / 'responses.json', results)
    summary = dict(revision=revision, total=len(dataset), hosted='NOT RUN: local baseline chosen by user',
                   clinical_validation=False, scope='fictional evidence handling, not clinical efficacy', arms={})
    for arm in ('strict', 'baseline'):
        positive = [r for c, r in zip(dataset, results) if c['answerable']]
        negative = [r for c, r in zip(dataset, results) if not c['answerable']]
        summary['arms'][arm] = dict(passed=sum(r[arm + '_score']['ok'] for r in results),
            answerable_total=len(positive), answerable_passed=sum(r[arm + '_score']['ok'] for r in positive),
            unanswerable_total=len(negative), unanswerable_passed=sum(r[arm + '_score']['ok'] for r in negative),
            failures=[r['id'] for r in results if not r[arm + '_score']['ok']])
    summary['clinical_release_gate'] = dict(synthetic_engineering_only=True, external_clinical_gold=False,
        clinical_reviewer_signoff=False, medical_source_truth_verified=False, ready_for_clinical_decisions=False)
    write(out / 'summary.json', summary)
    print(json.dumps(summary, indent=2))


if __name__ == '__main__':
    main()
