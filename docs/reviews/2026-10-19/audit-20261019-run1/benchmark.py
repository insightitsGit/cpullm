"""Reproducible small-corpus audit. Run with installed cpu-llm dependencies.

python docs/reviews/2026-10-19/benchmark.py --out ABSOLUTE_OUTPUT_DIRECTORY
Freezes src before importing it; creates one unique PostgreSQL namespace.
No existing documents are changed. Requires the normal local PostgreSQL service.
"""
import argparse
import hashlib
import importlib.metadata
import json
import os
from pathlib import Path
import platform
import shutil
import subprocess
import sys
import time
import uuid

CORPUS = [
    'The harbor kestrel is a small coastal falcon.',
    'The harbor kestrel nests in coastal cliffs.',
    'The harbor kestrel eats small fish.',
    'John ate a yellow apple in his house.',
    'Mary ate a red pear in her garden.',
    'Paris is the capital of France.',
    'Berlin is the capital of Germany.',
    'Rome is the capital of Italy.',
    'Business class is allowed for flights over six hours.',
    'The flight from Boston to Paris takes eight hours.',
    'The flight from Boston to Chicago takes two hours.',
    'The flight from Boston to Denver takes six hours.',
    'The blue heron is a large wading bird.',
    'The blue heron eats small fish.',
    'The blue heron nests in tall trees.',
    'The apple was yellow.',
    'The pear was red.',
]

# Gold evidence is declared before execution. Numbers are 1-based corpus rows.
# All evidence rows are required for multi-premise questions.
CASES = [
 ('identity', 'What is the harbor kestrel?', [1], 'small coastal falcon'),
 ('identity_paraphrase', 'Describe the harbor kestrel.', [1], 'small coastal falcon'),
 ('bird_location', 'Where does the harbor kestrel nest?', [2], 'coastal cliffs'),
 ('bird_diet', 'What does the harbor kestrel eat?', [3], 'small fish'),
 ('second_identity', 'What is the blue heron?', [13], 'large wading bird'),
 ('second_location', 'Where does the blue heron nest?', [15], 'tall trees'),
 ('second_diet', 'What does the blue heron eat?', [14], 'small fish'),
 ('event_color', 'What color was the apple John ate?', [4], 'yellow'),
 ('event_where', 'Where did John eat the apple?', [4], 'in his house'),
 ('event_who', 'Who ate the apple?', [4], 'John'),
 ('second_color', 'What color was the pear Mary ate?', [5], 'red'),
 ('second_where', 'Where did Mary eat the pear?', [5], 'in her garden'),
 ('second_who', 'Who ate the pear?', [5], 'Mary'),
 ('france', 'What is the capital of France?', [6], 'Paris'),
 ('germany', 'What is the capital of Germany?', [7], 'Berlin'),
 ('italy', 'What is the capital of Italy?', [8], 'Rome'),
 ('france_paraphrase', 'Which city is the capital of France?', [6], 'Paris'),
 ('rule_yes', 'Can I fly business class from Boston to Paris?', [9,10], 'YES: eight > six'),
 ('rule_below', 'Can I fly business class from Boston to Chicago?', [9,11], 'UNKNOWN: allowed-if does not imply forbidden otherwise'),
 ('rule_boundary', 'Can I fly business class from Boston to Denver?', [9,12], 'UNKNOWN: over excludes equality; no prohibition stated'),
 ('rule_negation', 'Is business class forbidden from Boston to Paris?', [9,10], 'NO: expressly allowed'),
 ('missing_country', 'What is the capital of Spain?', [], 'explicit nonanswer; corpus contains no Spain fact'),
 ('missing_attribute', 'How much does the harbor kestrel weigh?', [], 'explicit nonanswer; no weight stated'),
 ('missing_event', 'What color was the banana John ate?', [], 'explicit nonanswer; no banana event'),
 ('missing_agent', 'Who ate the banana?', [], 'explicit nonanswer; no banana event'),
 ('math_multiply', 'What is 17 times 24?', [], '408'),
 ('math_add', 'What is 125 plus 37?', [], '162'),
]

def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()

def main():
    p = argparse.ArgumentParser()
    p.add_argument('--out', required=True)
    p.add_argument('--repeats', type=int, default=3)
    args = p.parse_args()
    out = Path(args.out).resolve()
    out.mkdir(parents=True, exist_ok=False)
    root = Path(__file__).resolve().parents[3]
    snapshot = out / 'snapshot'
    shutil.copytree(root/'src', snapshot/'src', ignore=shutil.ignore_patterns('__pycache__', '*.pyc'))
    shutil.copy2(__file__, out/'benchmark.py')
    shutil.copy2(root/'pyproject.toml', snapshot/'pyproject.toml')
    manifest = {str(f.relative_to(snapshot)): digest(f) for f in snapshot.rglob('*') if f.is_file()}
    (out/'source-sha256.json').write_text(json.dumps(manifest, indent=2))
    os.environ['HF_HUB_OFFLINE'] = '1'
    os.environ['TRANSFORMERS_OFFLINE'] = '1'
    # Preserve any checkout model directory lookup despite freezing source elsewhere.
    if not os.environ.get('FACTBRIDGE_MODELS') and (root/'models').exists():
        os.environ['FACTBRIDGE_MODELS'] = str(root/'models')
    sys.path.insert(0, str(snapshot/'src'))
    os.chdir(out)
    from cpu_llm.pipeline import Appliance
    from cpu_llm.documents import SourceDocument
    metadata = {
        'utc': time.strftime('%Y-%m-%dT%H:%M:%SZ', time.gmtime()),
        'head': subprocess.check_output(['git','rev-parse','HEAD'],cwd=root,text=True).strip(),
        'dirty_status': subprocess.check_output(['git','status','--short'],cwd=root,text=True),
        'python': sys.version, 'platform': platform.platform(), 'processor': platform.processor(),
        'versions': {k: importlib.metadata.version(k) for k in ['cpu-llm','torch','transformers','sentence-transformers','numpy','psycopg']},
        'namespace': 'audit_' + uuid.uuid4().hex[:12], 'repeats': args.repeats,
        'source_manifest': 'source-sha256.json',
        'scope': 'Hand-authored synthetic smoke benchmark, not representative accuracy or a competitor benchmark. Serialized warmed requests; alternating baseline/full order by repeat. Gold evidence strict all-premise recall.',
        'corpus': [{'id':f'audit-notes-p{i:04}', 'text':t} for i,t in enumerate(CORPUS,1)],
        'cases': [{'id':k,'question':q,'gold_ids':[f'audit-notes-p{i:04}' for i in ids], 'expected':e, 'kind':'math' if k.startswith('math_') else 'missing' if k.startswith('missing_') else 'supported'} for k,q,ids,e in CASES],
    }
    (out/'protocol.json').write_text(json.dumps(metadata,indent=2))
    start=time.perf_counter()
    app=Appliance(namespace=metadata['namespace'])
    metadata['startup_seconds']=time.perf_counter()-start
    try:
        start=time.perf_counter()
        metadata['ingest']=app.ingest(SourceDocument('audit-notes', tuple(CORPUS)))
        metadata['ingest_seconds']=time.perf_counter()-start
        app.index.search('What is the harbor kestrel?',top_k=5)
        app.ask('What is the harbor kestrel?')
        with (out/'runs.jsonl').open('w',encoding='utf-8') as log:
            for rep in range(args.repeats):
                for case in metadata['cases']:
                    for mode in (['retrieval','pipeline'] if rep%2==0 else ['pipeline','retrieval']):
                        row={'case':case['id'],'repeat':rep,'mode':mode}
                        started=time.perf_counter()
                        try:
                            if mode=='retrieval':
                                hits=app.index.search(case['question'],top_k=5)
                                row['elapsed_ms']=(time.perf_counter()-started)*1000
                                row['hits']=[{k:h.get(k) for k in ['document_id','chunk_text','final_score']} for h in hits]
                            else:
                                r=app.ask(case['question'])
                                row['elapsed_ms']=(time.perf_counter()-started)*1000
                                row['result']={k:r.get(k) for k in ['message','original_message','answer','reply','related','passages','frame_result','math_result','audit_passed','shine_ok','typos','thinker_directive','realization_result','delivery_blocked']}
                        except Exception as exc:
                            row['elapsed_ms']=(time.perf_counter()-started)*1000
                            row['error']=f'{type(exc).__name__}: {exc}'
                        log.write(json.dumps(row,default=str)+'\n'); log.flush()
                    print(rep,case['id'],flush=True)
    finally:
        app.close()
        metadata['snapshot_verified']=all(digest(snapshot/k)==v for k,v in manifest.items())
        (out/'protocol.json').write_text(json.dumps(metadata,indent=2,default=str))
    print('DONE',out,flush=True)

if __name__=='__main__':
    main()
