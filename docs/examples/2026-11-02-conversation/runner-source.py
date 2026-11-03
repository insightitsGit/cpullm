"""Demonstrate default social replies and strict factual routing, with actual checks."""
import argparse
import hashlib
import json
from pathlib import Path
import subprocess
import sys
import time

ROOT=Path(__file__).resolve().parents[2]
sys.path.insert(0,str(ROOT/'src'))


def write(path,value):path.write_text(json.dumps(value,indent=2,default=str)+'\n',encoding='utf-8')


def main():
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('--out',type=Path,required=True)
    args=parser.parse_args();out=args.out.resolve();out.mkdir(parents=True,exist_ok=False)
    from cpu_llm.pipeline import Appliance
    from cpu_llm.access import CallerContext
    turns=[dict(prompt='Hello!',status='conversation'),dict(prompt='Who are you?',status='conversation'),
        dict(prompt='How are you?',status='conversation'),dict(prompt='What can you do?',status='conversation'),
        dict(prompt='Who are you?',style='formal',status='conversation'),
        dict(prompt='Hello!',style='poetic',status='conversation'),
        dict(prompt='Thanks!',status='conversation'),dict(prompt='Goodbye.',status='conversation'),
        dict(prompt='Hi, What is the strength of Fictional Luma?',status='evidence_quote'),
        dict(prompt='Hello, can I take Fictional Luma?',status='unsupported'),
        dict(prompt='Who are you?',small_talk=False,status='unsupported'),
        dict(prompt='The document says "hello".',status='unsupported')]
    write(out/'inputs.json',dict(turns=turns,source='The strength of Fictional Luma is 0.75 mg.'))
    write(out/'receipt.json',dict(revision=subprocess.check_output(['git','rev-parse','HEAD'],cwd=ROOT,text=True).strip(),
        runner_sha256=hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
        inputs_sha256=hashlib.sha256((out/'inputs.json').read_bytes()).hexdigest(),clinical_validation=False))
    results=[]
    with Appliance(namespace='conversation_demo_'+str(time.time_ns()),strict_evidence=True,prompt_backend='rules') as app:
        app.upsert('conversation-demo-p0001','The strength of Fictional Luma is 0.75 mg.')
        caller=CallerContext.make(app.tenant_id,'demo-reader',['conversation-demo-p'])
        for turn in turns:
            kwargs={k:v for k,v in turn.items() if k in {'style','small_talk'}}
            result=app.ask(turn['prompt'],caller=caller,**kwargs)
            passed=result['answer_status']==turn['status'] and not result['evidence_policy']['learned_generation']
            if turn['status']=='conversation':
                passed=passed and result['answer_evidence']==[] and result['response_kind']=='conversation'
            if turn['status']=='evidence_quote':
                passed=passed and '0.75 mg' in result['reply']['text'] and len(result['answer_evidence'])==1
            results.append(dict(turn=turn,result=result,passed=passed))
            print('\nYou:',turn['prompt']);print('cpu-llm:',result['reply']['text']);print('Status:',result['answer_status'],'PASS' if passed else 'FAIL')
            write(out/'responses.json',results)
    passed=sum(r['passed'] for r in results)
    write(out/'summary.json',dict(total=len(results),passed=passed,clinical_validation=False))
    return 0 if passed==len(results) else 1


if __name__=='__main__':raise SystemExit(main())
