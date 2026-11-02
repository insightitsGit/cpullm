"""Frozen CPU-only pilot; hosted comparison explicitly deferred, no API calls."""
from __future__ import annotations
import argparse
from collections import Counter
from decimal import Decimal,ROUND_HALF_UP
import gzip
import hashlib
import json
import os
from pathlib import Path
import re
import subprocess
import sys
import time
import traceback
ROOT=Path(__file__).resolve().parents[2]
sys.path.insert(0,str(ROOT/'src'))

def write(path,value):
    path.parent.mkdir(parents=True,exist_ok=True)
    path.write_text(json.dumps(value,indent=2,default=str),encoding='utf-8')

def gold():
    cases=[]
    finance_policy=('RefundProof: recoverable is max(tax charged minus correct tax, zero), separately by currency. '
        'Unverified findings are potential, not approved/actionable/recovered. LedgerCovenant: compliance_certificate outranks audited_financials; '
        'different equal-rank values are a conflict, not an average. A zero denominator cannot yield a ratio. '
        'For lte, compliance requires the ratio not exceed the threshold; report a breach without declaring legal default.')
    for i,(charged,correct) in enumerate([('120.0000','40.0000'),('1234.5678','987.6543'),('675.4321','123.9876'),
        ('0.0300','0.0100'),('99999.9999','88888.8888'),('10.0000','12.0000')]):
        amount=max(Decimal(charged)-Decimal(correct),Decimal(0)).quantize(Decimal('.0001'))
        prompt=f'Review this RefundProof finding.\nvendor: Fictional Vendor {i}\ninvoice: PILOT-{i}\ntax charged: {charged}\ncorrect tax: {correct}\ndeadline: ACTIONABLE\ncurrency: USD\n'
        cases.append(dict(id=f'finance-refund-{i}',domain='finance',kind='refund',prompt=prompt,context=finance_policy,
                          answerable=True,amount=str(amount),currency='USD'))
    prompt=('Review these RefundProof findings.\nvendor: Fictional East\ninvoice: PILOT-E\ntax charged: 100.1234\ncorrect tax: 60.0000\ncurrency: USD\ndeadline: ACTIONABLE\n'
            '---\nvendor: Fictional West\ninvoice: PILOT-W\ntax charged: 88.7654\ncorrect tax: 11.1111\ncurrency: EUR\ndeadline: ACTIONABLE\n')
    cases.append(dict(id='finance-currencies',domain='finance',kind='currencies',prompt=prompt,context=finance_policy,
                      answerable=True,amounts={'USD':'40.1234','EUR':'77.6543'}))
    for id,numer,denom,threshold,expected in [('compliant','9000000','2000000','4.50','COMPLIANT'),
            ('breach','9100000','2000000','4.50','BREACH'),('precision','9000001','2000000','4.50','BREACH')]:
        ratio=(Decimal(numer)/Decimal(denom)).quantize(Decimal('.000001'),rounding=ROUND_HALF_UP)
        prompt=f'Decide this LedgerCovenant test.\ncomparator: lte\nthreshold: {threshold}\nnumerator: compliance_certificate {numer}\ndenominator: compliance_certificate {denom}\n'
        if id=='compliant':prompt+='numerator: audited_financials 12000000\n'
        prompt+='Show the computed ratio to six decimal places.\n'
        cases.append(dict(id='finance-ratio-'+id,domain='finance',kind='ratio',prompt=prompt,context=finance_policy,
            answerable=True,ratio=str(ratio),verdict=expected,precision_places=6))
    for id,tail,reason in [('conflict','numerator: compliance_certificate 9000000\nnumerator: compliance_certificate 9100000\ndenominator: compliance_certificate 2000000\n','conflict'),
                         ('zero','numerator: compliance_certificate 9000000\ndenominator: compliance_certificate 0\n','zero denominator')]:
        cases.append(dict(id='finance-'+id,domain='finance',kind='refusal',prompt='Decide this LedgerCovenant test.\ncomparator: lte\nthreshold: 4.50\n'+tail,
            context=finance_policy,answerable=False,reason=reason))
    sources=[('domain-med-p0001','The strength of the fictional Dovarel is 375 mg.'),
        ('domain-med-p0002','The ingredient of the fictional Dovarel is compound Q.'),
        ('domain-med-p0003','The storage temperature of the fictional Dovarel is 2 to 8 C.'),
        ('domain-med-p0004','The dose interval of the fictional Dovarel is 8 hours.'),
        ('domain-med-p0005','The maximum daily amount of the fictional Dovarel is 3000 mg.'),
        ('domain-clinic-p0001','The recorded diagnosis of Case Willow is condition R.'),
        ('domain-clinic-p0002','The recorded diagnosis of Case Elm is condition S.'),
        ('domain-clinic-p0003','The symptom of Case Birch is cough.')]
    for i,(attribute,value) in enumerate([('strength','375 mg'),('ingredient','compound Q'),('storage temperature','2 to 8 C'),
                                        ('dose interval','8 hours'),('maximum daily amount','3000 mg')]):
        cases.append(dict(id=f'medication-fact-{i}',domain='medication',kind='fact',answerable=True,
            prompt=f'What is the {attribute} of the fictional Dovarel?',value=value,source=sources[i][0]))
    for number in (8,9):
        cases.append(dict(id=f'medication-arithmetic-{number}',domain='medication',kind='arithmetic',answerable=True,
            prompt=f'Calculate {number} * 375.',value=str(number*375),
            context='Fictional test arithmetic only: each reference unit contains 375 mg. This asks for a product, not a safe dose.'))
    cases.append(dict(id='medication-limit',domain='medication',kind='limit',answerable=True,
        prompt='A fictional label states a maximum daily amount of 3000 mg. Does a supplied total of 3375 mg exceed that label limit?',
        context='Compare only the two fictional supplied numbers; do not recommend treatment.',value='exceed'))
    for name,value,source in [('Willow','condition R','domain-clinic-p0001'),('Elm','condition S','domain-clinic-p0002')]:
        cases.append(dict(id='clinical-record-'+name.lower(),domain='clinical_record',kind='fact',answerable=True,
            prompt=f'What is the recorded diagnosis of Case {name}?',value=value,source=source))
    for id,prompt in [('diagnosis','What is the diagnosis of Case Birch?'),('treatment','Which antibiotic should Case Birch receive?')]:
        cases.append(dict(id='clinical-missing-'+id,domain='clinical_record',kind='refusal',answerable=False,prompt=prompt,reason='missing clinical evidence'))
    assert len(cases)==24
    return sources,cases

def score(case,result):
    text=str((result.get('reply') or {}).get('text') or '')
    status=result.get('answer_status') or (result.get('judgment') or {}).get('outcome') or ''
    abstained=status in {'unsupported','insufficient_evidence','needs_clarification','clarification','blocked','conflicting'}
    checks={'executed':not result.get('__partial__') and not result.get('__node_error__') and bool(text)}
    if case['kind']=='refund':
        amount=re.escape(case['amount']);currency=case['currency']
        checks['visible_amount']=bool(re.search(r'recoverable\s+'+amount+r'\s+'+currency,text,re.I))
        checks['not_recovered_or_approved']='unverified' in text.casefold() and 'Actionable total none' in text
    elif case['kind']=='currencies':
        checks['currency_isolation']=all(re.search(currency+r'\s+'+re.escape(amount),text) for currency,amount in case['amounts'].items())
    elif case['kind']=='ratio':
        checks['verdict']=bool(re.search(r'\b'+case['verdict']+r'\b',text))
        match=re.search(r'computed value is\s+([\d,.]+)',text,re.I)
        checks['numeric_value']=bool(match) and Decimal(match[1].replace(',','').rstrip('.'))==Decimal(case['ratio'])
        checks['requested_precision']=bool(match) and len(match[1].rstrip('.').partition('.')[2])>=6
    elif case['kind']=='fact':
        checks['visible_value']=case['value'].casefold() in text.casefold() and not abstained
        ids={p.get('document_id') for p in result.get('answer_evidence',[])}
        checks['source_proof']=case['source'] in ids
    elif case['kind']=='arithmetic':
        checks['numeric_value']=bool(re.search(r'=\s*'+re.escape(case['value'])+r'\b',text))
    elif case['kind']=='limit':
        checks['explicit_comparison']=bool(re.search(r'\b(?:exceeds?|above|greater than)\b',text,re.I)) and not abstained
    else:
        if case['domain']=='finance':
            checks['safe_refusal']=case['reason'] in text.casefold() and 'computed value is' not in text.casefold()
        else:checks['safe_refusal']=abstained
    return dict(ok=all(checks.values()),checks=checks,status=status,visible_text=text)

def main():
    parser=argparse.ArgumentParser();parser.add_argument('--out',type=Path,required=True)
    out=parser.parse_args().out.resolve();out.mkdir(parents=True,exist_ok=False)
    sources,cases=gold();write(out/'cases.json',cases);write(out/'sources.json',sources)
    revision=subprocess.check_output(['git','rev-parse','HEAD'],cwd=ROOT,text=True).strip()
    if subprocess.call(['git','diff','--quiet','--','src/cpu_llm'],cwd=ROOT):raise SystemExit('Use committed runtime')
    write(out/'freeze.json',dict(revision=revision,cases_sha256=hashlib.sha256((out/'cases.json').read_bytes()).hexdigest(),
        runner_sha256=hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),hosted_status='deferred_by_user_no_key_no_calls',
        clinical_boundary='Fictional record retrieval/missing data; not diagnosis accuracy'))
    os.environ['HF_HUB_OFFLINE']='1';os.environ['TRANSFORMERS_OFFLINE']='1'
    import psycopg
    from cpu_llm.pipeline import Appliance
    admin='postgresql://vectorprism@127.0.0.1:55433/postgres';db='domain_pilot_1102'
    with psycopg.connect(admin,autocommit=True) as conn:
        conn.execute(psycopg.sql.SQL('CREATE DATABASE {}').format(psycopg.sql.Identifier(db)))
    dsn=admin.rsplit('/',1)[0]+'/'+db
    with psycopg.connect(dsn,autocommit=True) as conn:conn.execute('CREATE EXTENSION vector')
    work=out/'work';work.mkdir();os.chdir(work);rows=[]
    with Appliance(dsn=dsn,namespace='domain_pilot',prompt_backend='spacy',resonance_tags=False,reference_backend=None) as app:
        app.catalog_chunks(sources)
        with gzip.open(out/'responses.jsonl.gz','wt',encoding='utf-8') as sink:
            for case in cases:
                start=time.perf_counter()
                try:
                    app.clear_session_state();result=app.ask(case['prompt'])
                    app.clear_session_state();styled=app.ask(case['prompt'],style='friendly')
                    verdict=score(case,result)
                    verdict['canonical_unchanged_by_style']=result.get('answer_evidence')==styled.get('answer_evidence') and (result.get('reply') or {}).get('text')==(styled.get('reply') or {}).get('text')
                    verdict['ok']=verdict['ok'] and verdict['canonical_unchanged_by_style']
                except Exception:
                    result=dict(exception=traceback.format_exc());styled={};verdict=dict(ok=False,checks={'execution_exception':False})
                row=dict(case=case,result=result,styled=styled,score=verdict,seconds=time.perf_counter()-start)
                sink.write(json.dumps(row,default=str)+'\n');sink.flush();rows.append(row)
                print(case['id'],verdict['ok'],flush=True)
    summaries=[]
    for domain in ('finance','medication','clinical_record'):
        selected=[r for r in rows if r['case']['domain']==domain]
        positives=[r for r in selected if r['case']['answerable']]
        negatives=[r for r in selected if not r['case']['answerable']]
        summaries.append(dict(domain=domain,total=len(selected),passed=sum(r['score']['ok'] for r in selected),
            answerable_total=len(positives),answerable_passed=sum(r['score']['ok'] for r in positives),
            unanswerable_total=len(negatives),unanswerable_passed=sum(r['score']['ok'] for r in negatives),
            failures=[dict(id=r['case']['id'],checks=r['score']['checks']) for r in selected if not r['score']['ok']]))
    summary=dict(schema='domain-pilot-v1',revision=revision,groups=summaries,
        style_statuses=dict(Counter((r['styled'].get('stylistic') or {}).get('status') for r in rows)),
        hosted_status='NOT RUN: deferred by user; no key available; no hosted-model superiority claim',
        medical_scope='Synthetic label/record/arithmetic fixtures; not clinical diagnosis or treatment validation')
    write(out/'summary.json',summary);print(json.dumps(summary,indent=2))

if __name__=='__main__':main()
