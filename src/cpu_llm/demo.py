"""Installed-package demos using fictional data and explicit expected results."""
import argparse
import hashlib
from importlib.resources import files
import json
from pathlib import Path
import uuid
from cpu_llm import __version__


def load_dataset(kind):
    if kind not in {'healthcare','conversation'}:raise ValueError('Unknown demo')
    return json.loads(files('cpu_llm').joinpath('data',kind+'-demo.json').read_text(encoding='utf-8'))


def verify(question,result,sources):
    text=(result.get('reply') or {}).get('text','')
    evidence=result.get('answer_evidence') or []
    checks=dict(status=result.get('answer_status')==question['expected_status'],
        visible_values=all(v in text for v in question['expected_values']),
        proof_retention=set(question['expected_proofs']) <= {p['document_id'] for p in evidence},
        no_learned_generation=(result.get('evidence_policy') or {}).get('learned_generation') is False)
    checks['proof_integrity']=all(p['document_id'] in sources and
        sources[p['document_id']][p['start']:p['end']]==p['quote'] and
        hashlib.sha256(sources[p['document_id']].encode('utf-8')).hexdigest()==p['chunk_sha256'] for p in evidence)
    if 'expected_kind' in question:
        checks['kind']=result.get('response_kind')==question['expected_kind']
        checks['not_document_evidence']=not evidence and result.get('answer') is None and result.get('audit_passed') is False
    if 'expected_tasks' in question:
        checks['tasks']=[t['status'] for t in result.get('task_results',[])]==question['expected_tasks']
    return dict(passed=all(checks.values()),checks=checks)


def write(path,value):path.write_text(json.dumps(value,indent=2,default=str)+'\n',encoding='utf-8')


def run(kind,out):
    data=load_dataset(kind)
    out=Path(out).resolve();out.mkdir(parents=True,exist_ok=False)
    write(out/'dataset.json',data)
    write(out/'receipt.json',dict(package_version=__version__,synthetic=True,clinical_validation=False,
        dataset_sha256=hashlib.sha256((out/'dataset.json').read_bytes()).hexdigest()))
    # Lazy imports keep --help and dataset inspection independent of DB/model startup.
    from cpu_llm.pipeline import Appliance
    from cpu_llm.documents import SourceDocument
    from cpu_llm.access import CallerContext
    sources={f"{d['name']}-p{i:04d}":p for d in data['documents'] for i,p in enumerate(d['paragraphs'],1)}
    results=[]
    with Appliance(namespace='package_demo_'+kind+'_'+uuid.uuid4().hex[:12],strict_evidence=True,prompt_backend='rules') as app:
        for doc in data['documents']:app.ingest(SourceDocument(doc['name'],tuple(doc['paragraphs'])))
        caller=CallerContext.make(app.tenant_id,'demo-reader',[d['name']+'-p' for d in data['documents']])
        for question in data['questions']:
            result=app.ask(question['prompt'],caller=caller,**question.get('kwargs',{}))
            verdict=verify(question,result,sources)
            results.append(dict(id=question['id'],prompt=question['prompt'],result=result,verification=verdict))
            print('\nYou:',question['prompt']);print('cpu-llm:',result['reply']['text'])
            print('Status:',result['answer_status'],'PASS' if verdict['passed'] else 'FAIL')
            write(out/'responses.json',results)
    passed=sum(r['verification']['passed'] for r in results)
    write(out/'summary.json',dict(package_version=__version__,total=len(results),passed=passed,
        synthetic=True,clinical_validation=False,failures=[r['id'] for r in results if not r['verification']['passed']]))
    print(f'\n{passed}/{len(results)} authored software checks passed. Not clinical validation.')
    return 0 if passed==len(results) else 1


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('kind',choices=['healthcare','conversation'])
    parser.add_argument('--out',type=Path,required=True,help='New directory for actual replies and checks')
    args=parser.parse_args()
    return run(args.kind,args.out)


if __name__=='__main__':raise SystemExit(main())
