import os,sys,types,subprocess,json,hashlib
from pathlib import Path
os.environ['FRONTIER_PARSER']='regex'
import cpu_llm.frontier as current
name='frontier_ec71024_reference'
reference=types.ModuleType(name);sys.modules[name]=reference
code=subprocess.check_output(['git','show','ec71024:src/cpu_llm/frontier.py']).decode('utf8')
exec(compile(code,name,'exec'),reference.__dict__)
def rows(*texts):
 return [dict(document_id=f'paper{i}-p0001',chunk_text=text) for i,text in enumerate(texts)]
cases=[
 ('capacity-chain','inference',rows('Memory bandwidth limits inference throughput.','Inference throughput drives serving revenue.','HBM supply constrains memory bandwidth.','Batch size limits inference throughput.')),
 ('three-edge','memory bandwidth research funding',rows('Memory bandwidth increases inference throughput.','Inference throughput increases serving revenue.','Serving revenue increases research funding.')),
 ('signed-pairs','model quality',rows('Training data increases model quality.','Measurement noise reduces model quality.','Model quality increases serving revenue.','Training data increases training cost.')),
]
results=[]
for label,topic,source in cases:
 old=reference.run_frontier(topic,source,limits=reference.FrontierLimits(max_path_edges=3,min_results=1),clock=lambda:0.)
 new=current.run_frontier(topic,source,limits=current.FrontierLimits(max_path_edges=3,min_results=1),clock=lambda:0.)
 fields=['candidates_generated','candidates_passed','survivors']
 equal=all(old[k]==new[k] for k in fields) and [(h['id'],h['text'],h['scores']) for h in old['hypotheses']]==[(h['id'],h['text'],h['scores']) for h in new['hypotheses']]
 assert equal and old['hypotheses'],(label,old,new)
 results.append(dict(case=label,unchanged=True,generated=new['candidates_generated'],survivors=new['survivors'],returned=len(new['hypotheses']),source_sha256=hashlib.sha256(json.dumps(source,sort_keys=True).encode()).hexdigest()))
 print(label,results[-1]['generated'],results[-1]['survivors'],results[-1]['returned'])
payload=dict(baseline='ec71024',comparison='working tree',frontier_sha256=hashlib.sha256(Path('src/cpu_llm/frontier.py').read_bytes()).hexdigest(),candidate_enumeration_unchanged=True,conditions='synthetic positive controls; regex parser; fixed clock; leading checks disabled to compare candidate generation',cases=results)
Path('docs/reviews/2026-11-21-latest-commits-review/candidate-retention.json').write_text(json.dumps(payload,indent=2)+'\n',encoding='utf8')
