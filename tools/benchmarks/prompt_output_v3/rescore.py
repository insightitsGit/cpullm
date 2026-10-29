"""Preserve original scores and rescore saved responses without querying runtime."""
from __future__ import annotations
import argparse
from collections import Counter
import hashlib
import json
from pathlib import Path
import sys
sys.path.insert(0,str(Path(__file__).resolve().parents[3]))
from tools.benchmarks.prompt_output_v3 import scorer_v2 as scorer

def main():
    parser=argparse.ArgumentParser();parser.add_argument('--out',type=Path,required=True)
    out=parser.parse_args().out
    if not (out/'summary.json').exists():raise SystemExit('Wait for original run to finish')
    target=out/'rescored-v2';target.mkdir(exist_ok=False)
    (target/'selftest.json').write_text(json.dumps(scorer.selftest(),indent=2),encoding='utf-8')
    (target/'scorer.sha256').write_text(hashlib.sha256(Path(scorer.__file__).read_bytes()).hexdigest(),encoding='utf-8')
    corpus=[json.loads(x) for x in (out/'gold/corpus.jsonl').read_text().splitlines()]
    summary=[];changed=[]
    for path in sorted((out/'results').glob('*.jsonl')):
        arm,split=path.stem.split('-',1)
        corrections=json.loads((out/f'ingest/{path.stem}.json').read_text())['corrections']
        documents={c['id']:dict(c) for c in corpus}
        for c in corpus:
            if c.get('correction'):
                documents[c['id']]['valid_until']=c['corrected_at']
                documents[corrections[c['id']]]=dict(c,text=c['correction'],valid_at=c['corrected_at'])
        with (target/path.name).open('w',encoding='utf-8') as f:
            for line in path.open(encoding='utf-8'):
                r=json.loads(line)
                if r['result'].get('benchmark_exception'):
                    verdict=dict(ok=False,errors=['execution_exception'])
                else:verdict=scorer.score(r['case'],r['result'],r['trace'],documents,corrections,arm)
                row={k:r[k] for k in ('id','kind','arm','split','family','seconds')}
                row.update(score=verdict)
                if r['score']['ok']!=verdict['ok']:
                    changed.append(dict(id=r['id'],arm=arm,original=r['score']['ok'],corrected=verdict['ok']))
                f.write(json.dumps(row)+'\n');summary.append(row)
    groups=[]
    for arm in ('rules','spacy'):
        for kind in ('core','routing','script'):
            rs=[r for r in summary if r['arm']==arm and r['kind']==kind]
            groups.append(dict(arm=arm,kind=kind,total=len(rs),passed=sum(r['score']['ok'] for r in rs),
                percent=round(100*sum(r['score']['ok'] for r in rs)/len(rs),2),
                failures=dict(Counter(e for r in rs for e in r['score']['errors']))))
    families=[]
    for arm in ('rules','spacy'):
        for family in sorted({r['family'] for r in summary if r['kind']=='core'}):
            rs=[r for r in summary if r['arm']==arm and r['kind']=='core' and r['family']==family]
            families.append(dict(arm=arm,family=family,total=len(rs),passed=sum(r['score']['ok'] for r in rs)))
    (target/'summary.json').write_text(json.dumps(dict(status='provisional',scorer=scorer.VERSION,
        groups=groups,families=families,changed=changed),indent=2),encoding='utf-8')
    print(json.dumps(groups,indent=2))

if __name__=='__main__':main()
