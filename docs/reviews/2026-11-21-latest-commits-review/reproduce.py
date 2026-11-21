import os, json
from types import SimpleNamespace
from unittest.mock import Mock
os.environ['FRONTIER_PARSER']='regex'
from cpu_llm.deepen import run_deepen, parse_hypothesis
from cpu_llm.frontier import run_frontier, FrontierLimits
from cpu_llm.pipeline import Appliance

def rows(*texts): return [dict(document_id=f'doc{i}-p0001',chunk_text=t) for i,t in enumerate(texts)]
def app(source):
 a=object.__new__(Appliance); a.tenant_id='review'; a.small_talk=False
 a.guard=SimpleNamespace(check=Mock(return_value=SimpleNamespace(decision='allow')))
 a.index=SimpleNamespace(strict_source_rows=Mock(return_value=(source,123)))
 return a
source=rows('Memory bandwidth reduces inference throughput.', 'Inference throughput increases serving revenue.')
r=run_deepen('Memory bandwidth may increase serving revenue through inference throughput.',source)
print('POLARITY',json.dumps([(l['source'],l['target'],l['status'],l['expected_relation']) for l in r['links']]),r['verdict'])
source=rows('Memory bandwidth increases inference throughput.', 'Inference throughput increases serving revenue.', 'Memory bandwidth does not reduce inference throughput.')
r=run_deepen('Memory bandwidth may increase serving revenue through inference throughput.',source)
print('NEGATED_OTHER_RELATION',json.dumps(r['links'][0]))
try:
 app(source).ask('Analyze this',deepen=dict(pattern='chain',anchors=['Memory bandwidth','serving revenue'],via=[1]))
except Exception as exc: print('BAD_API',type(exc).__name__,str(exc))
a=app(source); a.guard.check.return_value=SimpleNamespace(decision='deny')
r=a.ask('Deepen idea 1.',session_id='missing'); print('GUARD',r['answer_status'],'calls',a.guard.check.call_count)
source=rows('Memory bandwidth increases inference throughput.','Inference throughput increases serving revenue.','Serving revenue increases research funding.')
r=run_frontier('memory bandwidth research funding',source,limits=FrontierLimits(max_path_edges=3))
chains=[h for h in r['hypotheses'] if len(h['citations'])==3 and h['pattern']=='chain']
print('THREE_EDGE_CANDIDATES',len(chains))
if chains:
 h=chains[0]; d=run_deepen(h,source)
 print('THREE_EDGE',h['text'],'via',h['via'],'links',[(l['source'],l['target'],l['status']) for l in d['links']])
# Simulate a deadline expiring as the leading-check phase begins.
import cpu_llm.frontier as f
clock=[0.0]; original=f._check_leading
def expire(*args):
 clock[0]=100.
 return original(*args)
f._check_leading=expire
try:
 r=f.run_frontier('memory bandwidth',source,clock=lambda:clock[0],deepen_top=3)
finally:
 f._check_leading=original
print('LEADING_DEADLINE',r['incomplete'],r['stop_reason'],r['deepened'],r['budget_used'])
