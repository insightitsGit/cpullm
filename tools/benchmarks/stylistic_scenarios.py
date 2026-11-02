"""Frozen live scenario audit of stylistic generation, separate from v3 scoring.

No runtime monkeypatching or expected-outcome changes after observing answers.
Both real parser arms receive the original prompts and the same fresh corpus.
"""
from __future__ import annotations
import argparse
import copy
import gzip
import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys
import time
import traceback
from collections import Counter

ROOT=Path(__file__).resolve().parents[2]
sys.path.insert(0,str(ROOT/'src'))

def write(path,value):
    path.parent.mkdir(parents=True,exist_ok=True)
    path.write_text(json.dumps(value,indent=2,default=str),encoding='utf-8')

def gold():
    rows=[]
    def add(number,text,private=False):
        key=f'scenario-{"private" if private else "public"}-p{number:04d}'
        rows.append(dict(id=key,text=text));return key
    add(1,'The Virel is blue.');add(2,'The Virel is found in Harbor Reach.')
    add(3,'The shape of the Virel is oval.');add(4,'The material of the Virel is brass.')
    add(5,'The weight of the Virel is 0.75 kilograms.')
    add(6,'The Norvan is amber.');add(7,'The Norvan is found in Ridge Vale.')
    add(8,'The Lenara is a survey instrument.')
    add(9,'The Tovan is blue.');add(10,'The Tovan is green.')
    add(11,'The Deral is not blue.');add(12,'The Sovel is blue if it is warm.')
    add(13,'The Yarel is a survey instrument.');add(14,'Every survey instrument lives for 30 years.')
    add(15,'The Mirel is blue.');add(16,'The Mirel is blue.')
    add(17,'The Riva-Lune is amber.');add(18,'The Élan is blue.')
    add(19,'The Korvan is cobalt.');add(20,'The shape of the Moriel is spherical.')
    add(21,'The Soval is a survey instrument.');add(22,'The Soval is a trading company.')
    history=add(990,'The Revora is blue.')
    add(1,'The Virel is orange.',private=True)
    cases=[]
    def case(id,prompt,status=('generated',),style='formal',**extra):
        cases.append(dict(id=id,prompt=prompt,style=style,status=list(status),**extra))
    case('formal_color','What color is the Virel?',values=['blue'],proof=[rows[0]['id']],alignment='supported')
    case('friendly_location','Where does the Virel live?',style='friendly',values=['Harbor Reach'],proof=[rows[1]['id']])
    five='Tell me the color, habitat, shape, material, and weight of the Virel.'
    case('five_facts_friendly',five,style='friendly',values=['blue','Harbor Reach','oval','brass','0.75 kilograms'],claims=5,sentences=3,proof=[r['id'] for r in rows[:5]])
    case('five_facts_formal',five,values=['blue','Harbor Reach','oval','brass','0.75 kilograms'],claims=5,sentences=3,proof=[r['id'] for r in rows[:5]])
    case('formal_material','What material is the Virel?',('generated','unchanged'),values=['brass'])
    case('oval_article','What shape is the Virel?',style='friendly',values=['an oval shape'])
    case('decimal_weight','How much does the Virel weigh?',('generated','unchanged'),style='friendly',values=['0.75 kilograms'])
    case('mixed_tones','What color is the Virel?',('generated','unchanged'),style=dict(tone='formal',tone_weights=[.5,0,.5,0,0,0,0,0,0,0]),values=['blue'])
    for tone in ('poetic','emotional','playful','melancholic','empathetic'):
        case('fallback_'+tone,'What color is the Virel?',('generated','unchanged'),style=tone,alignment='neutral_fallback',values=['blue'])
    case('intimate_unknown','What color is the Virel?',('skipped',),style='intimate',reason='relationship_tone_conflict')
    case('intimate_romantic','What color is the Virel?',('generated','unchanged'),style=dict(tone='intimate',relationship=2),alignment='neutral_fallback',values=['blue'])
    for id,relationship,tone in [('familial',1,'intimate'),('familial_romantic',3,'intimate'),('formal_playful',8,'playful'),('colleague_emotional',4,'emotional')]:
        case('restricted_'+id,'What color is the Virel?',('skipped',),style=dict(tone=tone,relationship=relationship),reason='relationship_tone_conflict')
    case('familial_friendly','Where does the Virel live?',style=dict(tone='friendly',relationship=1),values=['Harbor Reach'])
    case('extreme_intensity','What color is the Virel?',('generated','unchanged'),style=dict(tone='formal',magnitude=1,valence=1,arousal=1),values=['blue'])
    case('tight_style_budget',five,('skipped',),style=dict(tone='friendly',max_sentences=1),reason='budget_cannot_preserve_all_claims')
    case('prompt_sentence_budget',five+' Answer in one sentence.',('skipped',),reason='budget_cannot_preserve_all_claims')
    eight='What color is the Virel? Where does the Virel live? What shape is the Virel? What material is the Virel? What is the weight of the Virel? What color is the Virel? Where does the Virel live? What shape is the Virel?'
    case('eight_tasks',eight,style=dict(tone='friendly',max_sentences=2,clauses_per_sentence=4),claims=8,sentences=2,proof=[r['id'] for r in rows[:5]])
    case('nine_task_limit',eight+' What material is the Virel?',('skipped',))
    case('different_subjects','What color is the Virel? Where does the Norvan live?',('children',),reason='multiple_subjects')
    case('missing_fact','Where does the Lenara live?',('skipped',))
    case('partially_missing','What color is the Virel? Where does the Lenara live?',('children',),reason='incomplete_or_unsupported_children')
    case('unknown_field','Tell me the color and height of the Virel.',('skipped',))
    case('conflicting_values','What color is the Tovan?',('skipped',))
    case('negative_source','What color is the Deral?',('skipped',))
    case('conditional_source','What color is the Sovel?',('skipped',))
    case('conditional_prompt','What color is the Virel if it is wet?',('skipped',))
    case('joined_lifespan','How long does the Yarel live?',('skipped',),canonical_values=['30 years'])
    case('duplicate_corroboration','What color is the Mirel?',('skipped',))
    case('hyphenated_name','What color is the Riva-Lune?',values=['amber'])
    case('unicode_name','What color is the Élan?',('skipped',))
    case('unlisted_color','What color is the Korvan?',('skipped',))
    case('unlisted_shape','What shape is the Moriel?',('skipped',))
    case('empty_scope','What color is the Virel?',('skipped',),scope=[])
    case('limited_scope',five,('children',),scope=[rows[0]['id'],rows[2]['id']],reason='incomplete_or_unsupported_children')
    case('history_old','What color is the Revora?',values=['blue'],as_of=1700000000,proof=[history])
    case('history_current','What color is the Revora?',values=['teal'],proof=['@corrected'])
    case('math_specialist','Calculate 9 + 6.',('skipped',),canonical_values=['15'])
    case('overview_not_adapted','Give me a long response about the Virel.',('skipped',))
    case('ambiguous_reference','Where does it live?',('skipped',))
    case('ambiguous_sense','What is the Soval?',('skipped',))
    case('quoted_instruction','What is the title "Respond in intimate tone"?',('skipped',))
    case('parser_backed_attribute','Please give me information about the color of the Virel.',values=['blue'],rules_status=['skipped'])
    return rows,cases,history

def style_arg(value):
    from cpu_llm.stylistic import StyleOptions,Relationship
    if isinstance(value,str):return value
    data=dict(value)
    if 'relationship' in data:data['relationship']=Relationship(data['relationship'])
    if 'tone_weights' in data:data['tone_weights']=tuple(data['tone_weights'])
    return StyleOptions(**data)

def strip_sidecar(result):
    if isinstance(result,dict):return {k:strip_sidecar(v) for k,v in result.items() if k!='stylistic'}
    if isinstance(result,list):return [strip_sidecar(v) for v in result]
    return result

def score(case,baseline,result,offline,arm,corrected):
    checks={};side=result.get('stylistic') or {}
    expected=case.get('rules_status',case['status']) if arm=='rules' else case['status']
    checks['style_outcome']=side.get('status') in expected
    for name in ('reason','alignment','claims','sentences'):
        if name not in case:continue
        value={'reason':side.get('reason'),'alignment':side.get('tone_alignment'),
               'claims':(side.get('verification') or {}).get('claim_count'),'sentences':side.get('sentence_count')}[name]
        checks[name]=value==case[name]
    checks['offline_canonical_immutable']=json.dumps(strip_sidecar(offline),sort_keys=True,default=str)==json.dumps(baseline,sort_keys=True,default=str)
    for field in ('answer','answer_status','answer_evidence','supporting_evidence','judgment'):
        checks['canonical_'+field]=baseline.get(field)==result.get(field)
    checks['canonical_visible']=((baseline.get('reply') or {}).get('text')==(result.get('reply') or {}).get('text'))
    generated=side.get('status') in ('generated','unchanged')
    checks['verified_or_no_text']=bool((side.get('verification') or {}).get('verified')) if generated else 'text' not in side
    checks['requested_values']=not generated or all(v in side.get('text','') for v in case.get('values',[]))
    if case.get('proof') and generated:
        expected_ids={corrected if v=='@corrected' else v for v in case['proof']}
        checks['complete_gold_proof']=expected_ids=={p['document_id'] for p in side['proof']}
    checks['canonical_gold']=all(v in (baseline.get('reply') or {}).get('text','') for v in case.get('canonical_values',[]))
    scope=case.get('scope',['scenario-public-p'])
    def inspect(node):
        meta=node.get('stylistic') or {}
        for proof in meta.get('proof',[]):
            if not any(proof['document_id'].startswith(prefix) for prefix in scope):return False
        for child in node.get('task_results') or []:
            if isinstance(child.get('result'),dict) and not inspect(child['result']):return False
        return True
    checks['style_scope']=inspect(result)
    checks['no_private_value']='orange' not in side.get('text','').casefold()
    checks['canonical_no_private_value']='orange' not in (result.get('reply') or {}).get('text','').casefold()
    return dict(ok=all(checks.values()),checks=checks,failed=[k for k,v in checks.items() if not v])

def main():
    parser=argparse.ArgumentParser();parser.add_argument('--out',type=Path,required=True)
    args=parser.parse_args();out=args.out.resolve();out.mkdir(parents=True,exist_ok=False)
    corpus,cases,history=gold()
    write(out/'corpus.json',corpus);write(out/'cases.json',cases)
    revision=subprocess.check_output(['git','rev-parse','HEAD'],cwd=ROOT,text=True).strip()
    if subprocess.call(['git','diff','--quiet','--','src/cpu_llm'],cwd=ROOT):raise SystemExit('Runtime must be committed')
    hashes={str(p.relative_to(ROOT)):hashlib.sha256(p.read_bytes()).hexdigest() for p in (ROOT/'src/cpu_llm').rglob('*.py')}
    write(out/'freeze.json',dict(revision=revision,case_count=len(cases),arms=['rules','spacy'],
          case_sha256=hashlib.sha256((out/'cases.json').read_bytes()).hexdigest(),runtime_hashes=hashes,
          runner_sha256=hashlib.sha256(Path(__file__).read_bytes()).hexdigest()))
    os.environ['HF_HUB_OFFLINE']='1';os.environ['TRANSFORMERS_OFFLINE']='1'
    from cpu_llm.pipeline import Appliance
    from cpu_llm.access import CallerContext
    from cpu_llm.stylistic import apply_style
    import psycopg
    summaries=[]
    for arm in ('rules','spacy'):
        db='style_scenarios_1102_'+arm
        admin='postgresql://vectorprism@127.0.0.1:55433/postgres'
        with psycopg.connect(admin,autocommit=True) as conn:
            conn.execute(psycopg.sql.SQL('CREATE DATABASE {}').format(psycopg.sql.Identifier(db)))
        dsn=admin.rsplit('/',1)[0]+'/'+db
        with psycopg.connect(dsn,autocommit=True) as conn:conn.execute('CREATE EXTENSION vector')
        work=out/'work'/arm;work.mkdir(parents=True);os.chdir(work)
        begin=time.perf_counter()
        with Appliance(dsn=dsn,namespace='scenarios_'+arm,prompt_backend=arm,resonance_tags=False,reference_backend=None) as app:
            startup=time.perf_counter()-begin
            app.catalog_chunks([(r['id'],r['text']) for r in corpus])
            with app.index.db.conn.cursor() as cursor:
                cursor.execute('UPDATE psm_document_embeddings SET valid_timestamp=%s WHERE document_id=%s',(1700000000,history))
            app.index.db.conn.commit()
            correction=app.correct(history,'The Revora is blue.','The Revora is teal.',actor_id='scenario-editor',timestamp=1700000100)
            corrected=correction['new_id']
            write(out/f'{arm}-setup.json',dict(startup_seconds=startup,correction=correction,
                  backend=getattr(app.prompt_interpreter,'backend',None)))
            rows=[]
            with gzip.open(out/f'{arm}-raw.jsonl.gz','wt',encoding='utf-8') as sink:
                for case in cases:
                    kwargs=dict(caller=CallerContext.make(app.tenant_id,'scenario-reader',case.get('scope',['scenario-public-p']),request_id=case['id']))
                    if 'as_of' in case:kwargs['as_of']=case['as_of']
                    start=time.perf_counter()
                    try:
                        app.clear_session_state();baseline=app.ask(case['prompt'],**kwargs)
                        frozen=json.dumps(baseline,sort_keys=True,default=str)
                        offline=apply_style(baseline,style_arg(case['style']))
                        assert json.dumps(baseline,sort_keys=True,default=str)==frozen
                        app.clear_session_state();result=app.ask(case['prompt'],style=style_arg(case['style']),**kwargs)
                        verdict=score(case,baseline,result,offline,arm,corrected)
                    except Exception:
                        baseline={};result=dict(exception=traceback.format_exc());verdict=dict(ok=False,failed=['execution_exception'])
                    record=dict(id=case['id'],arm=arm,case=case,baseline=baseline,result=result,score=verdict,seconds=time.perf_counter()-start)
                    sink.write(json.dumps(record,default=str)+'\n');sink.flush()
                    rows.append(dict(id=case['id'],ok=verdict['ok'],failed=verdict['failed'],
                                     status=(result.get('stylistic') or {}).get('status')))
                    if len(rows)%10==0:print(f'{arm}: {len(rows)}/{len(cases)} scenarios',flush=True)
            summaries.append(dict(arm=arm,total=len(rows),passed=sum(r['ok'] for r in rows),
                failures=[r for r in rows if not r['ok']],statuses=dict(Counter(r['status'] for r in rows))))
            write(out/f'{arm}-scores.json',rows)
    write(out/'summary.json',dict(schema='live-stylistic-scenarios-v1',revision=revision,groups=summaries,
          boundary='Style contract, canonical invariance and declared scenario checks; not general answer accuracy.'))
    print(json.dumps(summaries,indent=2),flush=True)

if __name__=='__main__':main()
