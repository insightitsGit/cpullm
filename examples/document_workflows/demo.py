"""Source-checkout demo: prompt tone is independent of source vocabulary."""
from pathlib import Path
import argparse
import json
import time

FACTS = [
    'Helios is a backup service.',
    'Helios stores encrypted backups.',
    'Helios uses PostgreSQL for metadata.',
    'Helios retains backups for 30 days.',
    'Helios runs backups every night.',
    'Helios does not support automatic regional failover.',
    'Helios restores files only if an operator approves.',
]

def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--out',type=Path,required=True)
    args=parser.parse_args();args.out.mkdir(parents=True,exist_ok=False)
    from cpu_llm.pipeline import Appliance
    assert not any('friendly' in fact.lower() for fact in FACTS)
    with Appliance(namespace='manual_demo_'+str(time.time_ns()),prompt_backend='rules',small_talk=False) as app:
        app.catalog_chunks([(f'manual-demo-p{i:04}',text) for i,text in enumerate(FACTS,1)])
        cases=[('friendly-article','Write a detailed article about Helios in a friendly tone.',{}),
               ('strict-report','Write a detailed report about Helios in a friendly tone.',{'strict_evidence':True})]
        for name,prompt,kwargs in cases:
            result=app.ask(prompt,**kwargs)
            assert len(result['answer_evidence'])==len(FACTS)
            if name=='friendly-article':
                assert result['stylistic']['verification']['verified']
                assert result['stylistic']['verification']['retained_literal_quotes']==1
            else:assert 'stylistic' not in result
            (args.out/(name+'.json')).write_text(json.dumps(result,indent=2),encoding='utf-8')
            (args.out/(name+'.md')).write_text(result['reply']['text'],encoding='utf-8')
            print(name+': '+result['answer_status'],flush=True)
    print('Saved results to '+str(args.out.resolve()))

if __name__=='__main__':main()
