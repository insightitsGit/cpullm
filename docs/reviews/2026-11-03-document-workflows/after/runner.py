"""Exploratory document workflow capture; fictional knowledge base."""
import sys,json,time,hashlib,subprocess
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT/'src'))
from cpu_llm.pipeline import Appliance
from cpu_llm.response_policy import classify_response_request

def main():
 out=ROOT/'build/document-workflow-20261103-after';out.mkdir(exist_ok=True)
 facts=[
  'Helios is a backup service.',
  'Helios stores encrypted backups.',
  'Helios uses PostgreSQL for metadata.',
  'Helios stores backup files in object storage.',
  'Helios verifies backup checksums.',
  'Helios retains backups for 30 days.',
  'Helios runs backups every night.',
  'Helios supports restoration by operators.',
  'Helios records restoration events in an audit log.',
  'Helios requires operator approval before deletion.',
  'Helios does not support automatic regional failover.',
  'Helios reports backup failures to operators.',
  'The Aster is blue.',
  'The material of the Aster is steel.'
 ]
 cases=[
  ('natural-report','Write a detailed report about Helios.',{}),
  ('overview-report','Give me a detailed overview of Helios as a Markdown report.',{}),
  ('natural-article','Write a detailed article about Helios.',{}),
  ('natural-design','Write a detailed design document about Helios.',{}),
  ('explicit-deep-report','Give me a detailed overview of Helios as a Markdown report.',{'deep':True}),
  ('twelve-sentences','Explain Helios in twelve sentences as bullet points.',{}),
  ('html-report','Give me a detailed overview of Helios as an HTML report.',{}),
  ('multi-section','What is Helios? What does Helios store? What database does Helios use? Present the answers as a Markdown table.',{}),
  ('styled-report','Give me a detailed overview of Helios as a Markdown report.',{'style':'friendly'}),
  ('strict-report','Write a detailed report about Helios.',{'strict_evidence':True}),
 ]
 (out/'inputs.json').write_text(json.dumps(dict(facts=facts,cases=cases),indent=2))
 (out/'freeze.json').write_text(json.dumps(dict(revision=subprocess.check_output(['git','rev-parse','HEAD'],cwd=ROOT,text=True).strip(),dirty_runtime=True,runner_sha256=hashlib.sha256(Path(__file__).read_bytes()).hexdigest()),indent=2))
 results=[]
 print('Loading appliance',flush=True)
 with Appliance(namespace='docwork_'+str(int(time.time())),prompt_backend='rules',small_talk=False) as app:
  app.catalog_chunks([(f'helios-manual-p{i:04}',t) for i,t in enumerate(facts,1)])
  for name,prompt,kwargs in cases:
   app.clear_session_state();start=time.perf_counter();r=app.ask(prompt,**kwargs)
   results.append(dict(id=name,prompt=prompt,kwargs=kwargs,seconds=time.perf_counter()-start,plan=classify_response_request(prompt),result=r))
   print(name,json.dumps(dict(status=r.get('answer_status'),words=len((r.get('reply')or{}).get('text','').split()),plan=r.get('response_plan'),style=r.get('stylistic'),text=(r.get('reply')or{}).get('text','')[:600]),default=str),flush=True)
   (out/'responses.json').write_text(json.dumps(results,indent=2,default=str))
 print('Complete',len(results),flush=True)
 

if __name__ == "__main__":
 main()
