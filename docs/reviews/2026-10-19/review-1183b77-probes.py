"""Live recheck of previous review plus missing-metric and entity-name cases."""
import json
import os
from pathlib import Path
import runpy
import sys
import traceback
import uuid

ROOT=Path(__file__).resolve().parents[3]
HERE=Path(__file__).resolve().parent
sys.path.insert(0,str(ROOT/'src'))
os.environ['HF_HUB_OFFLINE']='1'
os.environ['TRANSFORMERS_OFFLINE']='1'

def main():
    previous=runpy.run_path(str(HERE/'followup-probes-edf54ee.py'),run_name='prior_review')
    previous['main'].__globals__['OUT']=HERE/'recheck-1183b77-prior-probes.json'
    if '--extras-only' not in sys.argv:
        previous['main']()
    from cpu_llm.pipeline import Appliance, _prompt_entity, _passages_for_sentence
    from cpu_llm.documents import SourceDocument
    from fact_bridge import answer
    corpus=(
      'Business class is allowed for flights over six hours.',
      'The flight from Boston to Paris weighs three tons.',
      'Bank of America is a bank.',
      'Research and Development is a department.',
    )
    cases=[
      ('missing_metric','Can I fly business class from Boston to Paris?','UNKNOWN: duration is missing; do not raise'),
      ('name_with_of','Tell me about Bank of America.','Preserve the complete name and return the bank fact'),
      ('name_with_and','Tell me about Research and Development.','Preserve the complete department name'),
    ]
    observations=[]
    with Appliance(namespace='review_1183_'+uuid.uuid4().hex[:12]) as app:
        app.ingest(SourceDocument('review-notes',corpus))
        for case,q,expected in cases:
            row={'case':case,'question':q,'expected':expected,'corpus':corpus,'namespace':app.tenant_id}
            try:
                r=app.ask(q)
                row['result']={k:r.get(k) for k in ['answer','reply','model01','related','answer_status','verification_scope']}
                if not r.get('reply'):
                    row['failure_result']=r
            except Exception as exc:
                row['error']=f'{type(exc).__name__}: {exc}'
                row['traceback']=traceback.format_exc()
            observations.append(row)
            print(case,json.dumps({'error':row.get('error'),'reply':(row.get('result',{}).get('reply') or {}).get('text')}),flush=True)
    for q in [cases[1][1],cases[2][1]]:
        observations.append({'scope':'direct filter','question':q,'entity':_prompt_entity(q),
          'kept':_passages_for_sentence(q,[{'chunk_id':str(i),'chunk_text':t} for i,t in enumerate(corpus)])})
    try:
        direct=answer(cases[0][1],list(corpus[:2]),child_safety=False)
        observations.append({'scope':'public fact_bridge.answer','verdict':direct.verdict,'text':direct.text})
    except Exception as exc:
        observations.append({'scope':'public fact_bridge.answer','question':cases[0][1],
          'corpus':corpus[:2],'error':f'{type(exc).__name__}: {exc}','traceback':traceback.format_exc()})
    (HERE/'review-1183b77-probes.json').write_text(json.dumps(observations,indent=2,default=str),encoding='utf-8')

if __name__=='__main__': main()
