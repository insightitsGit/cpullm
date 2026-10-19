"""Transparent fixture scorer, not a general semantic correctness evaluator.

Run: python analyze.py OUTPUT_DIRECTORY
Review every unique reply in case-results.json before accepting the scores.
"""
import csv
import json
from pathlib import Path
import re
import statistics
import sys

PATTERNS = {
 'identity':r'harbor kestrel is a small coastal falcon',
 'identity_paraphrase':r'harbor kestrel is a small coastal falcon',
 'bird_location':r'coastal cliffs', 'bird_diet':r'eats small fish',
 'second_identity':r'blue heron is a large wading bird',
 'second_location':r'tall trees', 'second_diet':r'eats small fish',
 'event_color':r'apple John ate was yellow|John ate a yellow apple',
 'event_where':r'John ate the apple in his house|John ate a yellow apple in his house',
 'event_who':r'John ate (?:the|a yellow) apple',
 'second_color':r'pear Mary ate was red|Mary ate a red pear',
 'second_where':r'Mary ate the pear in her garden|Mary ate a red pear in her garden',
 'second_who':r'Mary ate (?:the|a red) pear',
 'france':r'Paris is the capital of France',
 'france_paraphrase':r'Paris is the capital of France',
 'germany':r'Berlin is the capital of Germany',
 'italy':r'Rome is the capital of Italy',
 'math_multiply':r'= 408\.', 'math_add':r'= 162\.',
}

def score(case, result):
    reply = result.get('reply') or {}
    text = reply.get('text') or ''
    k = case['id']
    if k in PATTERNS:
        return 'correct' if re.search(PATTERNS[k],text,re.I) else 'nonresponsive'
    if k.startswith('missing_'):
        return 'explicit_nonanswer' if re.search(r'no stored sentence|not enough|do not settle|cannot answer|don.t have enough',text,re.I) else 'nonresponsive'
    verdict = (reply.get('situation') or {}).get('verdict')
    expected = {'rule_yes':'YES','rule_below':'UNKNOWN','rule_boundary':'UNKNOWN','rule_negation':'NO'}[k]
    return 'correct' if verdict==expected else 'unsupported_or_wrong_rule_conclusion'

def main(out):
    protocol=json.loads((out/'protocol.json').read_text())
    runs=[json.loads(s) for s in (out/'runs.jsonl').read_text(encoding='utf-8').splitlines()]
    cases=[]
    for c in protocol['cases']:
        full=[r for r in runs if r['case']==c['id'] and r['mode']=='pipeline']
        base=[r for r in runs if r['case']==c['id'] and r['mode']=='retrieval']
        variants={json.dumps(r.get('result',{}).get('reply',{}).get('text'),ensure_ascii=False) for r in full}
        evidence=set(c['gold_ids'])
        b=base[0]; f=full[0]
        bi=[h['document_id'] for h in b.get('hits',[])]
        fi=[h.get('document_id') for h in f.get('result',{}).get('passages') or []]
        row={**c,'baseline_top1':(b.get('hits') or [{}])[0].get('chunk_text'),
             'baseline_ids':bi,'pipeline_ids':fi,
             'baseline_all_gold_at1':evidence.issubset(set(bi[:1])) if evidence else None,
             'baseline_all_gold_at5':evidence.issubset(set(bi[:5])) if evidence else None,
             'pipeline_all_gold_in_passages':evidence.issubset(set(fi)) if evidence else None,
             'outcomes':[score(c,r['result']) if 'result' in r else 'error' for r in full],
             'display_text':f.get('result',{}).get('reply',{}).get('text'),
             'unique_displays':[json.loads(s) for s in sorted(variants)],
             'audit_passed':f.get('result',{}).get('audit_passed'),
             'shine_ok':f.get('result',{}).get('shine_ok')}
        cases.append(row)
    facts=[c for c in cases if c['id'] in PATTERNS and not c['id'].startswith('math_')]
    evidence=[c for c in cases if c['gold_ids']]
    def passed(c): return c['outcomes'][0] in ['correct','explicit_nonanswer']
    def fraction(rows,fn): return {'passed':sum(bool(fn(c)) for c in rows),'total':len(rows)}
    latency={}
    for mode in ['retrieval','pipeline']:
        values=sorted(r['elapsed_ms'] for r in runs if r['mode']==mode and 'error' not in r)
        latency[mode]={'n':len(values),'median_ms':statistics.median(values),
                       'p95_ms_nearest_rank':values[max(0,__import__('math').ceil(.95*len(values))-1)],
                       'min_ms':min(values),'max_ms':max(values)}
    summary={'namespace':protocol['namespace'],'paragraphs':len(protocol['corpus'])+len(protocol.get('distractors',[])),
             'calls':len(runs),'errors':sum('error' in r for r in runs),
             'facts':fraction(facts,passed),'rules':fraction([c for c in cases if c['id'].startswith('rule_')],passed),
             'missing':fraction([c for c in cases if c['kind']=='missing'],passed),
             'math':fraction([c for c in cases if c['kind']=='math'],passed),
             'all_cases':fraction(cases,passed),
             'baseline_fact_gold_at1':fraction(facts,lambda c:c['baseline_all_gold_at1']),
             'baseline_fact_gold_at5':fraction(facts,lambda c:c['baseline_all_gold_at5']),
             'baseline_all_premises_at5':fraction(evidence,lambda c:c['baseline_all_gold_at5']),
             'pipeline_all_premises_in_passages':fraction(evidence,lambda c:c['pipeline_all_gold_in_passages']),
             'stable_display_cases':sum(len(c['unique_displays'])==1 for c in cases),
             'startup_seconds':protocol['startup_seconds'],'ingest_seconds':protocol['ingest_seconds'],
             'snapshot_verified':protocol['snapshot_verified'], 'latency':latency}
    (out/'case-results.json').write_text(json.dumps(cases,indent=2),encoding='utf-8')
    (out/'summary.json').write_text(json.dumps(summary,indent=2),encoding='utf-8')
    with (out/'comparison.csv').open('w',newline='',encoding='utf-8') as f:
        columns=['id','question','expected','baseline_all_gold_at1','baseline_all_gold_at5','pipeline_all_gold_in_passages','outcomes','baseline_top1','display_text']
        w=csv.DictWriter(f,columns,extrasaction='ignore');w.writeheader();w.writerows(cases)
    print(json.dumps(summary,indent=2))

if __name__=='__main__': main(Path(sys.argv[1]))
