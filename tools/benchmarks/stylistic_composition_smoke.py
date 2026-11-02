"""Fresh finite-construction evaluation plus replay of preserved canonical turns.

This does not rerun retrieval or revise v3 answer-quality scores.
"""
import argparse
from collections import Counter
import copy
import gzip
import hashlib
import json
from pathlib import Path
import re
import sys
import time
ROOT=Path(__file__).resolve().parents[2]
sys.path.insert(0,str(ROOT/'src'))
from cpu_llm.stylistic import apply_style,StyleOptions,Relationship
from cpu_llm.stylistic.profiles import TONES

def authored(subject,relation,text,key):
    proof=[dict(document_id=key,span=text)]
    return dict(answer_status='answered',reply=dict(text=text),judgment=dict(outcome='answered',verification='structural',
        evidence=copy.deepcopy(proof),answer_decision=dict(outcome='answered',text=text,proof=proof,
        request=dict(entity=subject,relation=relation,direction='subject',polarity='affirmative',quantifier_scope='individual'))))

def check_original(old,new):
    assert {k:v for k,v in new.items() if k not in ('stylistic','task_results')}=={k:v for k,v in old.items() if k!='task_results'}
    if old.get('task_results'):
        assert len(old['task_results'])==len(new['task_results'])
        for a,b in zip(old['task_results'],new['task_results']):
            assert {k:v for k,v in a.items() if k!='result'}=={k:v for k,v in b.items() if k!='result'}
            if isinstance(a.get('result'),dict):check_original(a['result'],b['result'])

def main():
    parser=argparse.ArgumentParser();parser.add_argument('--out',type=Path,required=True)
    out=parser.parse_args().out;out.mkdir(parents=True,exist_ok=True)
    if (out/'composition-evaluation.json').exists():raise SystemExit('Refusing to replace evaluation')
    counts=Counter();replayed=Counter();examples=[];started=time.perf_counter()
    with (out/'fresh.jsonl').open('w',encoding='utf-8') as sink:
        for i in range(20):
            name='Aster '+chr(65+i);color=['blue','green','white','purple'][i%4]
            shape=['round','oval','square','flat'][i%4];material=['steel','glass','wood','iron'][i%4]
            place='Harbor '+chr(65+i);weight=f'{10+i}.5 pounds'
            raw=[('has_color',f'The {name} is {color}.'),('lives_in',f'The {name} is found in {place}.'),
                 ('attribute:shape',f'The shape of the {name} is {shape}.'),
                 ('attribute:material',f'The material of the {name} is {material}.'),
                 ('attribute:weight',f'The weight of the {name} is {weight}.')]
            original=dict(answer_status='answered',reply=dict(text='Canonical tasks'),task_results=[
                dict(id=str(j),result=authored(name,r,t,f'fresh-{i}-p{j:04d}')) for j,(r,t) in enumerate(raw)])
            before=copy.deepcopy(original)
            for tone in TONES:
                output=apply_style(original,StyleOptions(tone=tone,relationship=Relationship.ROMANTIC))
                check_original(before,output);assert original==before
                side=output['stylistic'];assert side['status']=='generated',side
                assert side['sentence_count']==3 and side['verification']['claim_count']==5
                assert {p['span'] for p in side['proof']}=={t for _,t in raw}
                clauses=re.split(r'\.\s+|, and ',side['text'].removesuffix('.'))
                assert len(clauses)==5
                entity=re.escape(name)
                patterns=[rf'(?:The {entity} is {color}|The color of the {entity} is {color})',
                    rf'(?:The {entity} is found in {place}|You can find the {entity} in {place})',
                    rf'(?:The {entity} has {"an" if shape=="oval" else "a"} {shape} shape|The shape of the {entity} is {shape})',
                    rf'(?:The {entity} is made of {material}|The material of the {entity} is {material})',
                    rf'(?:The {entity} weighs {re.escape(weight)}|The weight of the {entity} is {re.escape(weight)})']
                assert all(re.fullmatch(pattern,text,re.I) for pattern,text in zip(patterns,clauses))
                counts[side['tone_alignment']]+=1
                sink.write(json.dumps(dict(id=i,tone=tone,result=side))+'\n')
                if len(examples)<2:examples.append(side['text'])
    with (out/'canonical-replay.jsonl').open('w',encoding='utf-8') as sink:
        for path in sorted((ROOT/'docs/benchmarks/2026-10-29-prompt-output-v3/results').glob('*.gz')):
            for line in gzip.open(path,'rt',encoding='utf-8'):
                row=json.loads(line);original=row['result'];before=copy.deepcopy(original)
                for tone in ('friendly','formal'):
                    output=apply_style(original,tone);check_original(before,output);assert original==before
                    side=output['stylistic'];replayed[side['status']]+=1
                    sink.write(json.dumps(dict(id=row['id'],arm=row['arm'],tone=tone,result=side))+'\n')
    summary=dict(schema='stylistic-composition-evaluation-v2',fresh_cases=sum(counts.values()),claims_per_fresh_case=5,
        fresh_alignment=dict(counts),canonical_replay_top_level_invocations=sum(replayed.values()),
        canonical_replay_statuses=dict(replayed),examples=examples,elapsed_seconds=time.perf_counter()-started,
        source_revision='dc8878b plus recorded working-tree source hashes',
        runtime_hashes={str(p.relative_to(ROOT)):hashlib.sha256(p.read_bytes()).hexdigest()
            for p in list((ROOT/'src/cpu_llm/stylistic').glob('*.py'))+[ROOT/'src/cpu_llm/pipeline.py',ROOT/'src/cpu_llm/prompt_ingestion.py']},
        limitation='Finite authored facts and preserved judgments; no measured improvement to retrieval or overall answer accuracy.')
    (out/'composition-evaluation.json').write_text(json.dumps(summary,indent=2),encoding='utf-8')
    print(json.dumps(summary,indent=2))

if __name__=='__main__':main()
