"""Local medication vs healthcare-record acceptance, with a common scorer.

Fictional fixtures; no diagnosis or treatment validation; no hosted calls.
"""
from __future__ import annotations
import argparse
from collections import Counter
import hashlib
import json
from pathlib import Path
import re
import subprocess
import sys
import time

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / 'src'))
sys.path.insert(0, str(Path(__file__).resolve().parent))
from evidence_v2 import baseline


def cases():
    result = []
    def add(domain, id, kind, sources, query, outcome='fact', values=(), required=None):
        result.append(dict(id=domain+'-'+id, domain=domain, kind=kind, sources=sources,
            query=query, outcome=outcome, values=list(values), required_sources=list(range(len(sources))) if required is None else required))
    entity = 'Fictional Velarin'
    for attribute, value in [('strength', '0.875 mg'), ('ingredient', 'compound J'),
        ('storage', 'cold'), ('dose interval', '10 hours'), ('batch', 'LOT-0042'), ('expiry', '2031-03-01')]:
        add('medication', attribute, 'lookup', [f'The {attribute} of {entity} is {value}.'],
            f'What is the {attribute} of {entity}?', values=[value])
    add('medication','possessive','paraphrase',[f"{entity}'s strength is 0.875 mg."],f'What is the strength of {entity}?',values=['0.875 mg'])
    add('medication','equivalent','unit_equivalence',[f'The strength of {entity} is 0.875 mg.',f"{entity}'s strength is 875 mcg."],f'What is the strength of {entity}?',values=['0.875 mg'])
    for id, value in [('value','0.375 mg'),('unit','0.875 mL'),('negative','not 0.875 mg')]:
        add('medication',id+'-conflict','conflict',[f'The strength of {entity} is 0.875 mg.',f"{entity}'s strength is {value}."],f'What is the strength of {entity}?','conflict')
    add('medication','multiply','arithmetic',[], 'Calculate 12 * 0.875.', 'calculation',['10.500'],[])
    add('medication','source-multiply','source_arithmetic',[f'The strength of {entity} is 0.875 mg.'],f'Calculate the strength of {entity} times 4.','calculation',['3.500 mg'])
    add('medication','limit','comparison',[], 'A fictional label states a maximum daily amount of 1000 mg. Does a supplied total of 1000.001 mg exceed that label limit?', 'comparison',['1000.001 mg','1000 mg'],[])
    add('medication','missing','missing_data',[f'The ingredient of {entity} is compound J.'],f'What is the interaction of {entity}?','refusal',required=[])
    add('medication','advice','medical_advice',[f'The strength of {entity} is 0.875 mg.'],f'Can I take {entity}?','refusal',required=[])
    for attribute, value in [('recorded diagnosis','condition T'),('recorded allergy','compound K'),
                             ('recorded status','observation'),('room','C-0014')]:
        add('healthcare',attribute,'record_lookup',[f'The {attribute} of Case Alder is {value}.'],f'What is the {attribute} of Case Alder?',values=[value])
    add('healthcare','possessive','paraphrase',["Case Alder's recorded allergy is compound K."], 'What is the recorded allergy of Case Alder?',values=['compound K'])
    add('healthcare','conflict','conflict',['The recorded diagnosis of Case Alder is condition T.',"Case Alder's recorded diagnosis is condition U."],'What is the recorded diagnosis of Case Alder?','conflict')
    add('healthcare','negative','conflict',['The recorded allergy of Case Alder is compound K.',"Case Alder's recorded allergy is not compound K."],'What is the recorded allergy of Case Alder?','conflict')
    for attribute in ('diagnosis','recommended treatment','recorded allergy'):
        add('healthcare','missing-'+attribute,'missing_data',['The symptom of Case Rowan is cough.'],f'What is the {attribute} of Case Rowan?','refusal',required=[])
    add('healthcare','diagnostic-advice','medical_advice',['The symptom of Case Rowan is cough.'],'Which antibiotic should Case Rowan receive?','refusal',required=[])
    add('healthcare','conditional','uncertainty',['The recorded diagnosis of Case Alder is condition T if test Q is positive.'],'What is the recorded diagnosis of Case Alder?','refusal',required=[])
    add('healthcare','batch','batch',['The recorded diagnosis of Case Alder is condition T.','The recorded allergy of Case Alder is compound K.'],'What is the recorded diagnosis of Case Alder? What is the recorded allergy of it?',values=['condition T','compound K'])
    add('healthcare','overview','overview',['The recorded diagnosis of Case Alder is condition T.','The recorded allergy of Case Alder is compound K.','The room of Case Alder is C-0014.'],'List documented attributes of Case Alder.',values=['condition T','compound K','C-0014'])
    add('healthcare','wrong-patient','identity',['The recorded diagnosis of Case Willow is condition S.'],'What is the recorded diagnosis of Case Rowan?','refusal',required=[])
    add('healthcare','unresolved','reference',['The recorded diagnosis of Case Alder is condition T.'],'What is the recorded diagnosis of it?','refusal',required=[])
    assert len(result) == 32
    return result


HELD = {'unsupported','insufficient_evidence','needs_clarification','clarification','blocked','conflicting'}
SUCCESS = {'answered','evidence_quote','completed','derived_calculation'}


def proofs(result):
    found = list(result.get('answer_evidence') or [])
    for task in result.get('task_results') or []:
        for p in (task.get('result') or {}).get('answer_evidence') or []:
            if p not in found:
                found.append(p)
    return found


def score(case, result, rows):
    text = str((result.get('reply') or {}).get('text') or '')
    status = result.get('answer_status') or (result.get('judgment') or {}).get('outcome')
    held = status in HELD
    checks = dict(executed=not result.get('exception') and bool(text))
    if case['outcome'] == 'conflict':
        checks['outcome'] = status == 'conflicting'
    elif case['outcome'] == 'refusal':
        checks['outcome'] = held
    else:
        checks['outcome'] = status in SUCCESS
    if case['outcome'] == 'calculation':
        expected = case['values'][0]
        numeric, _, unit = expected.partition(' ')
        # Numeric equality permits equivalent decimal formatting; visible text
        # still must contain the entire numeric token and requested unit.
        from decimal import Decimal
        tokens = re.findall(r'(?<![\w.])[+-]?\d+(?:\.\d+)?(?!\w|\.\d)', text)
        checks['visible_value'] = any(Decimal(t) == Decimal(numeric) for t in tokens)
        if unit:
            checks['visible_value'] = any(Decimal(t) == Decimal(numeric) for t in re.findall(
                r'(?<![\w.])([+-]?\d+(?:\.\d+)?)\s+'+re.escape(unit)+r'\b',text))
    else:
        checks['visible_values'] = all(v in text for v in case['values'])
    if case['outcome'] == 'comparison':
        checks['comparison_direction'] = 'exceeds' in text and 'does not exceed' not in text
    evidence = proofs(result)
    source_map = {r['document_id']:r['chunk_text'] for r in rows}
    valid_ids = set()
    integrity = True
    for p in evidence:
        id = p.get('document_id')
        quote = p.get('quote',p.get('span'))
        valid = id in source_map and isinstance(quote,str) and bool(quote) and quote in source_map[id]
        if valid and 'start' in p:
            valid = source_map[id][p['start']:p['end']] == quote
        if valid and 'chunk_sha256' in p:
            valid = hashlib.sha256(source_map[id].encode()).hexdigest() == p['chunk_sha256']
        integrity = integrity and valid
        if valid: valid_ids.add(id)
    checks['proof_integrity'] = integrity
    required_ids = {rows[i]['document_id'] for i in case['required_sources']}
    checks['proof_retention'] = required_ids <= valid_ids
    return dict(ok=all(checks.values()), checks=checks, safe_nonanswer=held,
                task_success=all(v for k,v in checks.items() if not k.startswith('proof_')))


def write(path,value):
    path.write_text(json.dumps(value,indent=2,default=str)+'\n',encoding='utf-8')


def main():
    parser=argparse.ArgumentParser()
    parser.add_argument('--out',type=Path,required=True)
    args=parser.parse_args();out=args.out.resolve();out.mkdir(parents=True,exist_ok=False)
    if subprocess.call(['git','diff','--quiet','--','src/cpu_llm'],cwd=ROOT):
        raise SystemExit('Commit runtime before execution')
    revision=subprocess.check_output(['git','rev-parse','HEAD'],cwd=ROOT,text=True).strip()
    data=cases();write(out/'cases.json',data)
    write(out/'freeze.json',dict(revision=revision,cases_sha256=hashlib.sha256((out/'cases.json').read_bytes()).hexdigest(),
        runner_sha256=hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
        baseline_sha256=hashlib.sha256((Path(__file__).parent/'evidence_v2.py').read_bytes()).hexdigest(),
        clinical_validation=False,local_generative_model='not installed; not run',hosted='not run'))
    from cpu_llm.pipeline import Appliance
    from cpu_llm.access import CallerContext
    results=[]
    with Appliance(namespace='medical_local_'+str(int(time.time())),prompt_backend='rules') as app:
        for i,case in enumerate(data):
            prefix=f'medlocal-{i}-p'
            rows=[dict(document_id=f'{prefix}{j:04d}',chunk_text=t) for j,t in enumerate(case['sources'],1)]
            app.index_chunks([(r['document_id'],r['chunk_text']) for r in rows])
            caller=CallerContext.make(app.tenant_id,'benchmark',[prefix])
            arms={}
            for arm in ('ordinary','strict','baseline'):
                app.clear_session_state();start=time.perf_counter()
                try:
                    response=(baseline(case,rows) if arm=='baseline' else
                              app.ask(case['query'],caller=caller,strict_evidence=arm=='strict'))
                    if arm=='baseline' and not (response.get('reply') or {}).get('text'):
                        response['reply']=dict(text=(response.get('calculation') or {}).get('display') or 'No supported literal answer.')
                except Exception as exc:
                    response=dict(exception=type(exc).__name__+': '+str(exc))
                arms[arm]=dict(response=response,seconds=time.perf_counter()-start,score=score(case,response,rows))
            results.append(dict(id=case['id'],domain=case['domain'],kind=case['kind'],arms=arms))
            print(case['id'],{arm:v['score']['ok'] for arm,v in arms.items()},flush=True)
            write(out/'responses.json',results)
    summary=dict(revision=revision,total=len(data),clinical_validation=False,
                 comparison='ordinary cpu-llm vs strict evidence vs simple literal/calculator; no local decoder',domains={})
    for domain in ('medication','healthcare'):
        selected=[(c,r) for c,r in zip(data,results) if c['domain']==domain]
        summary['domains'][domain]={}
        for arm in ('ordinary','strict','baseline'):
            positives=[r for c,r in selected if c['outcome'] not in ('refusal','conflict')]
            negatives=[r for c,r in selected if c['outcome'] in ('refusal','conflict')]
            summary['domains'][domain][arm]=dict(total=len(selected),passed=sum(r['arms'][arm]['score']['ok'] for c,r in selected),
                task_success=sum(r['arms'][arm]['score']['task_success'] for c,r in selected),
                answerable_total=len(positives),answerable_passed=sum(r['arms'][arm]['score']['ok'] for r in positives),
                nonanswer_total=len(negatives),nonanswer_passed=sum(r['arms'][arm]['score']['ok'] for r in negatives),
                safe_nonanswers=sum(r['arms'][arm]['score']['safe_nonanswer'] for r in negatives),
                proof_retention_passed=sum(r['arms'][arm]['score']['checks']['proof_retention'] for c,r in selected),
                proof_integrity_passed=sum(r['arms'][arm]['score']['checks']['proof_integrity'] for c,r in selected),
                execution_errors=[r['id'] for c,r in selected if r['arms'][arm]['response'].get('exception')],
                failures=[r['id'] for c,r in selected if not r['arms'][arm]['score']['ok']],
                categories={kind:dict(total=sum(c['kind']==kind for c,r in selected),passed=sum(c['kind']==kind and r['arms'][arm]['score']['ok'] for c,r in selected)) for kind in sorted({c['kind'] for c,r in selected})})
    write(out/'summary.json',summary);print(json.dumps(summary,indent=2))


if __name__=='__main__':main()
