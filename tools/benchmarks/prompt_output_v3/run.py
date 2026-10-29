"""Execute frozen public v3 cases. Report incomplete protocol gates explicitly.

Run with the separately installed snapshot wheel, never an editable runtime.
"""
from __future__ import annotations
import argparse
from collections import Counter
import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys
import time
import traceback

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT))
from tools.benchmarks.prompt_output_v3 import gold, scorer

def write(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, indent=2, default=str), encoding='utf-8')

def load(path):
    return [json.loads(line) for line in path.read_text(encoding='utf-8').splitlines()]

def main():
    parser=argparse.ArgumentParser()
    parser.add_argument('--out', type=Path, required=True)
    args=parser.parse_args(); out=args.out.resolve()
    if (out/'results').exists():
        raise SystemExit('Refusing to overwrite a recorded run')
    fixtures=scorer.selftest()
    manifest=gold.dump(out/'gold')
    write(out/'scorer-selftest.json',fixtures)
    write(out/'evaluator-freeze.json',{
        p.name:hashlib.sha256(p.read_bytes()).hexdigest()
        for p in Path(__file__).parent.glob('*.py')})
    os.environ['HF_HUB_OFFLINE']='1'
    os.environ['TRANSFORMERS_OFFLINE']='1'
    import cpu_llm
    from cpu_llm.pipeline import Appliance
    from cpu_llm.access import CallerContext
    import psycopg
    if 'site-packages' not in str(cpu_llm.__file__):
        raise RuntimeError('Benchmark requires installed wheel')
    write(out/'environment/runtime.json',dict(module=cpu_llm.__file__,python=sys.version,
          revision=(out/'snapshot/HEAD.txt').read_text().strip(),gold=manifest))
    corpus=load(out/'gold/corpus.jsonl')
    cases=load(out/'gold/cases.jsonl')+load(out/'gold/routing_cases.jsonl')
    scripts=load(out/'gold/scripts.jsonl')
    totals=[]
    for arm in ('rules','spacy'):
        for split in ('development','holdout'):
            db=f'cpullm_v3_291029_{arm}_{split}'
            admin='postgresql://vectorprism@127.0.0.1:55433/postgres'
            with psycopg.connect(admin,autocommit=True) as conn:
                conn.execute(psycopg.sql.SQL('CREATE DATABASE {}').format(psycopg.sql.Identifier(db)))
            dsn=admin.rsplit('/',1)[0]+'/'+db
            with psycopg.connect(dsn,autocommit=True) as conn:
                conn.execute('CREATE EXTENSION vector')
            work=out/'work'/arm/split;work.mkdir(parents=True)
            os.chdir(work)
            begin=time.perf_counter()
            with Appliance(dsn=dsn,namespace='v3',prompt_backend=arm,resonance_tags=False,reference_backend=None) as app:
                startup=time.perf_counter()-begin
                begin=time.perf_counter()
                receipt=app.catalog_chunks([(d['id'],d['text']) for d in corpus])
                documents={d['id']:dict(d) for d in corpus};corrections={}
                for d in corpus:
                    if not d.get('correction'):continue
                    with app.index.db.conn.cursor() as cursor:
                        cursor.execute('UPDATE psm_document_embeddings SET valid_timestamp=%s WHERE document_id=%s',
                                       (d['valid_at'],d['id']))
                    app.index.db.conn.commit()
                    r=app.correct(d['id'],d['text'],d['correction'],actor_id='benchmark-editor',timestamp=d['corrected_at'])
                    corrections[d['id']]=r['new_id']
                    documents[d['id']]['valid_until']=d['corrected_at']
                    documents[r['new_id']]=dict(d,text=d['correction'],valid_at=d['corrected_at'])
                write(out/f'ingest/{arm}-{split}.json',dict(startup_seconds=startup,seconds=time.perf_counter()-begin,
                      receipt=receipt,corrections=corrections))
                trace=[]
                for name in ('search','search_allowed'):
                    original=getattr(app.index,name)
                    def wrapper(*a,_fn=original,_name=name,**kw):
                        start=time.perf_counter()
                        result=_fn(*a,**kw)
                        trace.append(dict(event='search',method=_name,seconds=time.perf_counter()-start,
                                          query=str(a[0]) if a else str(kw.get('query'))))
                        return result
                    setattr(app.index,name,wrapper)
                result_path=out/f'results/{arm}-{split}.jsonl';result_path.parent.mkdir(exist_ok=True)
                def ask(case,case_id,kind,session_id=None):
                    trace.clear();kw=dict(case.get('api') or {});kw['session_id']=session_id
                    if case.get('caller') is not None:
                        c=case['caller'];kw['caller']=CallerContext.make('v3',c.get('id','reader'),c['sources'])
                    if case.get('as_of') is not None:kw['as_of']=case['as_of']
                    start=time.perf_counter()
                    try:
                        result=app.ask(case['prompt'],**kw)
                        verdict=scorer.score(case,result,trace,documents,corrections,arm)
                    except Exception:
                        result=dict(benchmark_exception=traceback.format_exc())
                        verdict=dict(ok=False,errors=['execution_exception'])
                    row=dict(id=case_id,kind=kind,arm=arm,split=split,family=case.get('family'),
                             seconds=time.perf_counter()-start,case=case,result=result,trace=list(trace),score=verdict)
                    with result_path.open('a',encoding='utf-8') as f:f.write(json.dumps(row,default=str)+'\n')
                    totals.append(dict(id=case_id,kind=kind,arm=arm,split=split,family=case.get('family'),
                                       seconds=row['seconds'],ok=verdict['ok'],errors=verdict['errors']))
                    if len(totals)%10==0:print(f'{len(totals)} requests recorded; {arm}/{split}',flush=True)
                for case in cases:
                    if case['split']!=split:continue
                    app.clear_session_state()
                    ask(case,case['id'],'routing' if case['id'].startswith('route-') else 'core')
                class Clock:
                    now=0.0
                    def __call__(self):return self.now
                clock=Clock()
                from cpu_llm.request_planner import RequestSessions
                if not hasattr(app,'request_sessions'):
                    app.request_sessions=RequestSessions()
                for store in (app.clarifications,app.references,app.request_sessions):
                    store.clock=clock
                for script in scripts:
                    if script['split']!=split:continue
                    app.clear_session_state()
                    for i,case in enumerate(script['turns']):
                        if case.get('action')=='advance_clock':clock.now+=case['clock_delta']
                        if case.get('action')=='reset_sessions':app.clear_session_state()
                        ask(case,f'{script["id"]}-{i}','script',script['id'])
    write(out/'scores.json',totals)
    summary=[]
    for arm in ('rules','spacy'):
        for kind in ('core','routing','script'):
            rows=[r for r in totals if r['arm']==arm and r['kind']==kind]
            summary.append(dict(arm=arm,kind=kind,total=len(rows),passed=sum(r['ok'] for r in rows),
                                failures=dict(Counter(e for r in rows for e in r['errors']))))
    write(out/'summary.json',dict(status='provisional_public_run',groups=summary,
          incomplete_gates=['gold/scorer independent review','16 controlled fixtures','setup matrix',
                            'known failure replay','warm timing repetitions','process restart lifecycle',
                            'full failure adjudication'],optional_not_run=['scale','resonance']))
    print(json.dumps(summary,indent=2),flush=True)

if __name__=='__main__':main()
