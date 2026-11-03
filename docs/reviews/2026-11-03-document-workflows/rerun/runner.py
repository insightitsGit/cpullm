"""Repeat the article/report integration examples with exact source checks."""
from pathlib import Path
import sys,json,time,hashlib,subprocess
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT/'src'))

def main():
 from cpu_llm.pipeline import Appliance
 facts=json.loads((ROOT/'build/document-workflow-20261103-final/inputs.json').read_text())['facts']
 out=ROOT/'build'/('article-report-rerun-'+str(int(time.time())));out.mkdir()
 source={f'rerun-manual-p{i:04}':t for i,t in enumerate(facts,1)}
 results=[]
 print('Loading database-backed appliance...',flush=True)
 with Appliance(namespace='article_report_'+str(time.time_ns()),prompt_backend='rules',small_talk=False) as app:
  app.catalog_chunks(list(source.items()))
  for genre in ('article','report'):
   prompt=f'Write a detailed {genre} about Helios.'
   result=app.ask(prompt)
   proofs=result['answer_evidence']
   assert len(proofs)==12,(genre,len(proofs))
   assert result['answer_status']=='evidence_quote'
   assert not result['document']['coverage']['missing_sections']
   for proof in proofs:
    assert proof['quote']==source[proof['document_id']]
    assert proof['chunk_sha256']==hashlib.sha256(proof['quote'].encode()).hexdigest()
   assert not any('Aster' in p['quote'] for p in proofs)
   (out/f'{genre}.md').write_text(result['reply']['text'],encoding='utf-8')
   results.append(dict(prompt=prompt,result=result,checks_passed=True))
   print(genre.upper(),json.dumps(dict(status=result['answer_status'],quotes=len(proofs),sections=[s['title'] for s in result['document']['sections']],missing=result['document']['coverage']['missing_sections'])),flush=True)
 (out/'responses.json').write_text(json.dumps(results,indent=2),encoding='utf-8')
 (out/'receipt.json').write_text(json.dumps(dict(revision=subprocess.check_output(['git','rev-parse','HEAD'],text=True).strip(),dirty_runtime=True,runner_sha256=hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),runtime_sha256={str(p.relative_to(ROOT)):hashlib.sha256(p.read_bytes()).hexdigest() for p in (ROOT/'src/cpu_llm').rglob('*.py')}),indent=2))
 print('RESULTS_DIRECTORY='+str(out),flush=True)

if __name__=='__main__':main()
