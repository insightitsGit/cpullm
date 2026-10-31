"""Run every test file sequentially in four fresh pytest processes.

This avoids carrying all model/test allocations through one long process.
It does not change runtime settings or turn off live tests.
"""
import json
from pathlib import Path
import subprocess
import sys
import xml.etree.ElementTree as ET

ROOT=Path(__file__).resolve().parents[2]

def main():
    out=Path(sys.argv[1]).resolve()
    files=sorted((ROOT/'tests').rglob('test_*.py'))
    groups=[files[i:i+19] for i in range(0,len(files),19)]
    totals=dict(passed=0,skipped=0,xfail=0,failures=0,errors=0,tests=0)
    runs=[]
    for i,group in enumerate(groups):
        log=out/f'suite-part-{i}.log';xml=out/f'suite-part-{i}.xml'
        if log.exists() or xml.exists():raise SystemExit('Refusing to overwrite suite parts')
        print(f'Running suite part {i+1}/{len(groups)}: {len(group)} files',flush=True)
        with log.open('w',encoding='utf-8') as sink:
            proc=subprocess.run([sys.executable,'-m','pytest','-q','--tb=short',*[str(p.relative_to(ROOT)) for p in group],f'--junitxml={xml}'],cwd=ROOT,stdout=sink,stderr=subprocess.STDOUT)
        run=dict(part=i,exit_code=proc.returncode,files=[str(p.relative_to(ROOT)) for p in group])
        if xml.exists():
            tree=ET.parse(xml);attrs=list(tree.iter('testsuite'))[0].attrib
            counts={k:int(attrs[k]) for k in ('tests','skipped','failures','errors')}
            expected=sum(n.get('type')=='pytest.xfail' for n in tree.iter('skipped'))
            counts['xfail']=expected;counts['passed']=counts['tests']-counts['skipped']-counts['failures']-counts['errors']
            counts['skipped']-=expected
            run['counts']=counts
            for key in totals:totals[key]+=counts[key]
        runs.append(run)
        print(json.dumps(run.get('counts',run)),flush=True)
    result=dict(schema='isolated-full-suite-v1',totals=totals,runs=runs,
        complete=all(r['exit_code']==0 and 'counts' in r for r in runs),
        reason='Initial monolithic pytest run exhausted host memory; every test file rerun in isolated batches.')
    (out/'suite-summary.json').write_text(json.dumps(result,indent=2),encoding='utf-8')
    print(json.dumps(result['totals']),flush=True)
    return 0 if result['complete'] else 1

if __name__=='__main__':raise SystemExit(main())
