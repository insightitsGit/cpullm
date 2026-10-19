"""Additional review cases beyond the original 27-question regression set.

Run from the repository with dependencies and cached models available.
Creates two fresh namespaces; changes no existing source documents.
"""
import json
import os
from pathlib import Path
import sys
import uuid

os.environ['HF_HUB_OFFLINE']='1'
os.environ['TRANSFORMERS_OFFLINE']='1'
ROOT=Path(__file__).resolve().parents[3]
sys.path.insert(0,str(ROOT/'src'))
OUT=ROOT/'docs/reviews/2026-10-19/followup-probes-edf54ee.json'

def main():
    from cpu_llm.pipeline import Appliance, _passages_for_sentence
    from cpu_llm.documents import SourceDocument
    from cpu_llm.answerability import assess
    results=[]
    configurations=[
        ('allowance',[
          'Business class is allowed for flights over six hours.',
          'The flight from Boston to Paris takes eight hours.',
          'The harbor kestrel watches a fish that weighs two kilograms.',
          'The harbor kestrel eats a fish that nests in coastal cliffs.',
          'The harbor kestrel watches a heron eat small fish.',
          'The harbor kestrel is a small coastal falcon.',
          'The picnic was held beside a harbor.',
          'Ada is a mathematician.',
        ],[
          ('permission_not_obligation','Is business class required from Boston to Paris?','UNKNOWN: permission does not require business class'),
          ('weight_wrong_subject','How much does the harbor kestrel weigh?','No bird weight stated; fish weight is not a binding'),
          ('nest_wrong_subject','Where does the harbor kestrel nest?','No bird nesting location stated; fish location is not a binding'),
          ('model01_partial_overlap','Tell me about the harbor kestrel.','Do not include the picnic as an answer about the bird'),
          ('model01_short_subject','Tell me about Ada.','Retain available Ada evidence in Model01 input'),
        ]),
        ('prohibition',[
          'Business class is forbidden for flights over six hours.',
          'The flight from Boston to Paris takes eight hours.',
        ],[
          ('prohibition_confirmation','Is business class forbidden from Boston to Paris?','YES: stored prohibition applies'),
        ]),
    ]
    for config,texts,cases in configurations:
        namespace='review_edf_'+uuid.uuid4().hex[:12]
        with Appliance(namespace=namespace) as app:
            receipt=app.ingest(SourceDocument('review-notes',tuple(texts)))
            for case,q,expected in cases:
                r=app.ask(q)
                results.append({'case':case,'namespace':namespace,'corpus':texts,'question':q,'expected':expected,
                    'result':{k:r.get(k) for k in ['message','reply','answer','answer_status','answer_evidence','verification_scope','related','model01','frame_result','typos','audit_passed','shine_ok']}})
                print(case,json.dumps({'text':(r.get('reply') or {}).get('text'),'status':r.get('answer_status'),'model_status':(r.get('model01') or {}).get('status')}),flush=True)
                OUT.write_text(json.dumps(results,indent=2,default=str),encoding='utf-8')
    for q,text in [
      ('How much does the harbor kestrel weigh?','The harbor kestrel watches a fish that weighs two kilograms.'),
      ('Where does the harbor kestrel nest?','The harbor kestrel eats a fish that nests in coastal cliffs.'),
      ('What does the harbor kestrel eat?','The harbor kestrel watches a heron eat small fish.'),
    ]:
        results.append({'scope':'direct assessment module','question':q,'text':text,'assessment':assess(q,[text])})
    OUT.write_text(json.dumps(results,indent=2,default=str),encoding='utf-8')

if __name__=='__main__': main()
