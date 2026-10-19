"""Live regression checks for the missing measurement and complete-name fixes."""
import json
import os
from pathlib import Path
import sys
import uuid

ROOT=Path(__file__).resolve().parents[3]
sys.path.insert(0,str(ROOT/'src'))
os.environ['HF_HUB_OFFLINE']='1'
os.environ['TRANSFORMERS_OFFLINE']='1'

def main():
    from cpu_llm.documents import SourceDocument
    from cpu_llm.pipeline import Appliance
    from fact_bridge import answer

    corpus=(
      'Business class is allowed for flights over six hours.',
      'The flight from Boston to Paris weighs three tons.',
      'Bank of America is a bank.',
      'Research and Development is a department.',
      'The harbor kestrel is a small coastal falcon.',
      'The picnic was held beside a harbor.',
      'Ada is a mathematician.',
    )
    namespace='review_9d6_'+uuid.uuid4().hex[:12]
    cases=[
      ('missing_metric','Can I fly business class from Boston to Paris?',None),
      ('internal_of','Tell me about Bank of America.','Bank of America is a bank.'),
      ('internal_and','Tell me about Research and Development.','Research and Development is a department.'),
      ('short_name','Tell me about Ada.','Ada is a mathematician.'),
      ('exclude_picnic','Tell me about the harbor kestrel.','The harbor kestrel is a small coastal falcon.'),
    ]
    rows=[]
    direct=answer(cases[0][1],list(corpus[:2]),child_safety=False)
    assert direct.verdict=='UNKNOWN' and 'duration' in direct.text.lower()
    with Appliance(namespace=namespace) as app:
        app.ingest(SourceDocument('review-notes',corpus))
        for case,q,expected in cases:
            r=app.ask(q)
            text=str((r.get('reply') or {}).get('text') or '')
            assert text and not r.get('__partial__') and not r.get('__node_error__'), (case,r.get('__node_error__'))
            if expected:
                assert expected in text,(case,text)
                assert 'picnic' not in text.casefold(),(case,text)
                assert 'business class' not in text.casefold(),(case,text)
            else:
                situation=(r.get('reply') or {}).get('situation') or {}
                assert situation.get('verdict')=='UNKNOWN',(case,text,situation)
                assert 'duration' in text.casefold(),(case,text)
            rows.append({'case':case,'question':q,'expected':expected,'passed':True,
              'result':{k:r.get(k) for k in ['reply','answer','model01','related','__partial__','__node_error__']}})
            print(case,'PASS',text,flush=True)
    data={'commit':'9d6fbe8','namespace':namespace,'corpus':corpus,
      'public_function':{'verdict':direct.verdict,'text':direct.text},'cases':rows}
    Path(__file__).with_suffix('.json').write_text(json.dumps(data,indent=2,default=str),encoding='utf-8')

if __name__=='__main__': main()
