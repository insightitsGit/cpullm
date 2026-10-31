"""Measure companion-generation coverage on preserved v3 canonical responses.

No retrieval is rerun and no old benchmark score is overwritten. This is an
output-node replay, not a new end-to-end answer-quality benchmark.
"""
import argparse
from collections import Counter
import gzip
import hashlib
import json
from pathlib import Path
import re
import sys
import time

ROOT=Path(__file__).resolve().parents[2]
sys.path.insert(0,str(ROOT/'src'))
from cpu_llm.stylistic import apply_style

def main():
    parser=argparse.ArgumentParser();parser.add_argument('--out',type=Path,required=True)
    args=parser.parse_args();args.out.mkdir(parents=True,exist_ok=False)
    counters=Counter();examples=[]
    files=ROOT/'docs/benchmarks/2026-10-29-prompt-output-v3/results'
    started=time.perf_counter()
    with (args.out/'replay.jsonl').open('w',encoding='utf-8') as sink:
        for path in sorted(files.glob('*.gz')):
            for line in gzip.open(path,'rt',encoding='utf-8'):
                row=json.loads(line);original=row['result'];before=json.dumps(original,sort_keys=True)
                for profile in ('formal','friendly'):
                    begin=time.perf_counter();output=apply_style(original,profile)
                    elapsed=time.perf_counter()-begin
                    assert json.dumps(original,sort_keys=True)==before
                    assert json.dumps({k:v for k,v in output.items() if k not in ('stylistic','task_results')},sort_keys=True)==json.dumps({k:v for k,v in original.items() if k!='task_results'},sort_keys=True)
                    # Recurse through batch sidecars while independently asserting
                    # every canonical field of each child stayed unchanged.
                    def inspect(old,new):
                        meta=new['stylistic'];counters[meta['status']]+=1
                        if meta['status']=='children':
                            assert len(old['task_results'])==len(new['task_results'])
                            for a,b in zip(old['task_results'],new['task_results']):
                                if isinstance(a.get('result'),dict):inspect(a['result'],b['result'])
                            return
                        assert {k:v for k,v in new.items() if k!='stylistic'}==old
                        if meta['status']=='generated':
                            assert meta['text'] not in ('',old['reply']['text'])
                            proof={(p['document_id'],p['span']) for p in meta['proof']}
                            accepted={(p['document_id'],p['span']) for p in old['judgment']['evidence']}
                            assert proof==accepted
                            # Independent expected closed-surface check against the
                            # original accepted sentence, not the verifier's boolean.
                            sentence=old['judgment']['answer_decision']['text']
                            if profile=='formal':
                                m=re.fullmatch(r'(.+) is ([a-z]+)\.',sentence)
                                entity=m[1];expected='The color of '+('the '+entity[4:] if entity.startswith('The ') else entity)+' is '+m[2]+'.'
                            else:
                                m=re.fullmatch(r'(.+) is found in (.+)\.',sentence)
                                entity=m[1];expected='You can find '+('the '+entity[4:] if entity.startswith('The ') else entity)+' in '+m[2]+'.'
                            assert meta['text']==expected
                            if len(examples)<8:examples.append(dict(id=row['id'],arm=row['arm'],profile=profile,canonical=sentence,generated=meta['text']))
                    inspect(original,output)
                    sink.write(json.dumps(dict(id=row['id'],arm=row['arm'],profile=profile,seconds=elapsed,stylistic=output['stylistic']))+'\n')
    summary=dict(schema='stylistic-smoke-v1',source_requests=680,profile_invocations=1360,
        statuses_including_batch_children=dict(counters),examples=examples,elapsed_seconds=time.perf_counter()-started,
        interpretation='Coverage and invariance replay on saved judgments; no new answer-accuracy or retrieval score.',
        runtime_hashes={str(p.relative_to(ROOT)):hashlib.sha256(p.read_bytes()).hexdigest()
                        for p in list((ROOT/'src/cpu_llm/stylistic').glob('*.py'))+[ROOT/'src/cpu_llm/pipeline.py']})
    (args.out/'summary.json').write_text(json.dumps(summary,indent=2),encoding='utf-8')
    print(json.dumps(summary,indent=2))

if __name__=='__main__':main()
