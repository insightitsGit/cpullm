"""Run the checked-in fictional healthcare demo using the real strict API."""
from __future__ import annotations
import argparse
import hashlib
import json
from pathlib import Path
import subprocess
import sys
import time

ROOT=Path(__file__).resolve().parents[2]
sys.path.insert(0,str(ROOT/'src'))
DATASET=Path(__file__).with_name('dataset.json')


def check(question,result,sources):
    text=(result.get('reply') or {}).get('text','')
    evidence=result.get('answer_evidence') or []
    checks=dict(status=result.get('answer_status')==question['expected_status'],
        visible_values=all(value in text for value in question['expected_values']),
        proof_retention=set(question['expected_proofs']) <= {p['document_id'] for p in evidence},
        no_learned_generation=(result.get('evidence_policy') or {}).get('learned_generation') is False)
    checks['proof_integrity']=all(p['document_id'] in sources and
        sources[p['document_id']][p['start']:p['end']]==p['quote'] and
        hashlib.sha256(sources[p['document_id']].encode('utf-8')).hexdigest()==p['chunk_sha256'] for p in evidence)
    if 'expected_tasks' in question:
        checks['tasks']=[t['status'] for t in result.get('task_results',[])]==question['expected_tasks']
    return dict(passed=all(checks.values()),checks=checks)


def write(path,value):path.write_text(json.dumps(value,indent=2,default=str)+'\n',encoding='utf-8')


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--out',type=Path,required=True,help='New directory for actual responses and checks')
    args=parser.parse_args();out=args.out.resolve();out.mkdir(parents=True,exist_ok=False)
    data=json.loads(DATASET.read_text(encoding='utf-8'))
    from cpu_llm.documents import SourceDocument
    from cpu_llm.pipeline import Appliance
    from cpu_llm.access import CallerContext
    sources={f"{doc['name']}-p{i:04d}":text for doc in data['documents'] for i,text in enumerate(doc['paragraphs'],1)}
    write(out/'receipt.json',dict(dataset_sha256=hashlib.sha256(DATASET.read_bytes()).hexdigest(),
        runner_sha256=hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),synthetic=True,clinical_validation=False,
        revision=subprocess.check_output(['git','rev-parse','HEAD'],cwd=ROOT,text=True).strip()))
    results=[]
    with Appliance(namespace='healthcare_demo_'+str(time.time_ns()),strict_evidence=True,prompt_backend='rules') as app:
        for doc in data['documents']:app.ingest(SourceDocument(doc['name'],tuple(doc['paragraphs'])))
        caller=CallerContext.make(app.tenant_id,'demo-reader',[doc['name']+'-p' for doc in data['documents']])
        for question in data['questions']:
            result=app.ask(question['prompt'],caller=caller)
            verification=check(question,result,sources)
            results.append(dict(id=question['id'],prompt=question['prompt'],result=result,verification=verification))
            print('\nYou:',question['prompt'])
            print('cpu-llm:',result['reply']['text'])
            print('Status:',result['answer_status'],'| expected-result check:', 'PASS' if verification['passed'] else 'FAIL')
            write(out/'responses.json',results)
    passed=sum(row['verification']['passed'] for row in results)
    write(out/'summary.json',dict(total=len(results),passed=passed,synthetic=True,clinical_validation=False,
        failures=[r['id'] for r in results if not r['verification']['passed']]))
    print(f'\n{passed}/{len(results)} authored software checks passed. Not a clinical accuracy score.')
    return 0 if passed==len(results) else 1


if __name__=='__main__':raise SystemExit(main())
