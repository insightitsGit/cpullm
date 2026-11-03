"""Capture real public-API tone examples with proofs; fictional demonstration facts."""
from __future__ import annotations
import argparse
import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys
import time
from urllib.parse import parse_qsl, urlencode, urlsplit, urlunsplit

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'src'))

SOURCES=[('tone-chat-p0001','The Aster is blue.'),
         ('tone-chat-p0002','The Aster is found in coastal waters.'),
         ('tone-chat-p0003','The shape of the Aster is round.'),
         ('tone-chat-p0004','The material of the Aster is steel.'),
         ('tone-chat-p0005','The weight of the Aster is 12.5 pounds.'),
         ('tone-label-p0001','The strength of Fictional DemoMed is 0.75 mg.')]


def write(path,value):path.write_text(json.dumps(value,indent=2,default=str)+'\n',encoding='utf-8')


def main():
    parser=argparse.ArgumentParser();parser.add_argument('--out',type=Path,required=True)
    parser.add_argument('--dsn',help='PostgreSQL URI; defaults to VECTORPRISM_PG_DSN or the library development database')
    args=parser.parse_args()
    import psycopg
    from cpu_llm.retrieval import LOCAL_PG_DSN
    dsn=args.dsn or os.environ.get('VECTORPRISM_PG_DSN') or LOCAL_PG_DSN
    # Fail before writing run artifacts or loading models when storage is unavailable.
    # Retain the timeout for the appliance's subsequent namespace connections.
    uri=urlsplit(dsn)
    if uri.scheme not in ('postgres','postgresql'):
        parser.error('Use a postgresql:// URI for --dsn or VECTORPRISM_PG_DSN')
    query=dict(parse_qsl(uri.query));query['connect_timeout']='5'
    dsn=urlunsplit(uri._replace(query=urlencode(query)))
    print('Checking PostgreSQL and pgvector availability...',flush=True)
    try:
        with psycopg.connect(dsn) as conn:
            available=conn.execute("SELECT 1 FROM pg_extension WHERE extname='vector'").fetchone()
            if not available:parser.error('The selected database needs the vector extension enabled')
    except psycopg.Error:
        parser.error('Database connection failed within the connection timeout. Start PostgreSQL/pgvector and set VECTORPRISM_PG_DSN or --dsn; no model initialization was attempted.')
    out=args.out.resolve();out.mkdir(parents=True,exist_ok=False)
    from cpu_llm.pipeline import Appliance
    from cpu_llm.stylistic import StyleOptions,Relationship
    cases=[dict(id='formal-color',prompt='What color is the Aster?',style='formal'),
           dict(id='friendly-location',prompt='Where does the Aster live?',style='friendly'),
           dict(id='analytical-weight',prompt='What is the weight of the Aster?',style='analytical'),
           dict(id='five-fact-composition',prompt='Tell me the color, habitat, shape, material, and weight of the Aster.',
                style=dict(tone='friendly',max_sentences=3,clauses_per_sentence=2)),
           dict(id='poetic-fallback',prompt='What color is the Aster?',style='poetic'),
           dict(id='relationship-restriction',prompt='What color is the Aster?',
                style=dict(tone='intimate',relationship=int(Relationship.FAMILIAL))),
           dict(id='strict-label',prompt='What is the strength of Fictional DemoMed?',style='friendly',strict_evidence=True),
           dict(id='finance-boundary',prompt='Decide this LedgerCovenant test.\nthreshold: 4.50\nnumerator: compliance_certificate 9000001\ndenominator: compliance_certificate 2000000\n',style='friendly',finance=True)]
    write(out/'inputs.json',dict(sources=SOURCES,cases=cases))
    write(out/'freeze.json',dict(revision=subprocess.check_output(['git','rev-parse','HEAD'],cwd=ROOT,text=True).strip(),
        runner_sha256=hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
        inputs_sha256=hashlib.sha256((out/'inputs.json').read_bytes()).hexdigest(),facts='fictional; not medication guidance'))
    results=[]
    print('Database ready. Loading the appliance and cached model assets...',flush=True)
    with Appliance(dsn=dsn,namespace='tone_chat_'+str(int(time.time())),prompt_backend='rules') as app:
        print('Appliance ready. Ingesting six fictional source facts...',flush=True)
        app.catalog_chunks(SOURCES)
        for case in cases:
            spec=case['style']
            if isinstance(spec,dict):
                spec=dict(spec)
                if 'relationship' in spec:spec['relationship']=Relationship(spec['relationship'])
                spec=StyleOptions(**spec)
            kwargs={key:case[key] for key in ('finance','strict_evidence') if key in case}
            app.clear_session_state();canonical=app.ask(case['prompt'],**kwargs)
            app.clear_session_state();result=app.ask(case['prompt'],style=spec,**kwargs)
            side=result.get('stylistic') or {}
            same=(canonical.get('reply') or {}).get('text')==(result.get('reply') or {}).get('text')
            same_proofs=canonical.get('answer_evidence')==result.get('answer_evidence')
            if not same or not same_proofs:raise AssertionError('style changed canonical output/proofs')
            results.append(dict(id=case['id'],prompt=case['prompt'],requested_style=case['style'],
                canonical_unchanged=same,canonical_proofs_unchanged=same_proofs,result=result))
            print(case['id'],side.get('status','disabled'),side.get('tone_alignment'),side.get('text') or side.get('reason'),flush=True)
            write(out/'responses.json',results)
    write(out/'summary.json',dict(turns=len(results),canonical_unchanged=all(r['canonical_unchanged'] for r in results),
        canonical_proofs_unchanged=all(r['canonical_proofs_unchanged'] for r in results),
        examples=[dict(id=r['id'],status=(r['result'].get('stylistic') or {}).get('status','disabled'),
                       tone_alignment=(r['result'].get('stylistic') or {}).get('tone_alignment')) for r in results]))


if __name__=='__main__':main()
