"""Small live feature demonstration; not a representative accuracy benchmark.

Uses a unique namespace and synthetic notes; never changes existing sources.
Run from the cpullm checkout with the installed dependencies and local Postgres.
"""
import json
import time
import uuid
from pathlib import Path

OUT = Path(__file__).with_name('feature-demonstration-rerun-' + uuid.uuid4().hex[:12] + '.json')
PASSAGES = (
    'The harbor kestrel is a small coastal falcon.',
    'The harbor kestrel nests in coastal cliffs.',
    'The harbor kestrel eats small fish.',
    'John ate a yellow apple in his house.',
    'Business class is allowed for flights over six hours.',
    'The flight from Boston to Paris takes eight hours.',
    'The flight from Boston to Chicago takes two hours.',
)


def main():
    from cpu_llm.documents import SourceDocument
    from cpu_llm.pipeline import Appliance

    namespace = 'feature_demo_' + uuid.uuid4().hex[:12]
    data = {'namespace': namespace, 'passages': list(PASSAGES), 'results': [],
            'scope': 'Live Appliance on a seven-paragraph synthetic corpus. Not an accuracy benchmark.'}
    print('Opening isolated namespace:', namespace, flush=True)
    started = time.perf_counter()
    app = Appliance(namespace=namespace)
    data['startup_seconds'] = round(time.perf_counter()-started, 3)
    try:
        receipt = app.ingest(SourceDocument('feature-notes', PASSAGES))
        data['ingest'] = receipt
        cases = [
            ('definition', 'What is the harbor kestrel?', {}),
            ('color', 'What color was the apple John ate?', {}),
            ('location', 'Where did John eat the apple?', {}),
            ('agent', 'Who ate the apple?', {}),
            ('missing_role', 'What color was the pear John ate?', {}),
            ('summary', 'Summarize the harbor kestrel.', {}),
            ('sources', 'Cite sources for the harbor kestrel.', {}),
            ('deep_search', 'Deep search the harbor kestrel.', {}),
            ('creative', 'Imagine the harbor kestrel.', {}),
            ('comparison', 'Compare the harbor kestrel and John.', {}),
            ('document', 'Write an email about the harbor kestrel.', {}),
            ('math', 'What is 17 times 24?', {}),
            ('rule', 'Can I fly business class from Boston to Paris?', {}),
            ('outside_corpus', 'What is the capital of France?', {}),
            ('n0_realizer', 'What color was the apple John ate?', {'realization':'evidence_neural'}),
        ]
        for name, prompt, kwargs in cases:
            start = time.perf_counter()
            try:
                result = app.ask(prompt, **kwargs)
                reply = result.get('reply') or {}
                row = {'case':name,'prompt':prompt,'kwargs':kwargs,
                       'elapsed_ms':round((time.perf_counter()-start)*1000,1),
                       'display_text':reply.get('text'), 'answer':result.get('answer'),
                       'related':[{'id':x.get('chunk_id'),'text':x.get('chunk_text')} for x in result.get('related') or []],
                       'audit_passed':result.get('audit_passed'), 'shine_ok':result.get('shine_ok'),
                       'shine_enforced':result.get('shine_enforced'),'delivery_blocked':result.get('delivery_blocked'),
                       'situation':reply.get('situation'), 'draft':reply.get('draft'),
                       'frame':result.get('frame_result'), 'math':result.get('math_result'),
                       'brief':result.get('brief'), 'comparison':result.get('comparison'),
                       'imagination':result.get('imagination'),
                       'possibility_count':result.get('possibility_count'),
                       'realization':result.get('realization_result'), 'typos':result.get('typos'),
                       'thinker_directive':result.get('thinker_directive')}
            except Exception as exc:
                row={'case':name,'prompt':prompt,'error':type(exc).__name__+': '+str(exc)}
            data['results'].append(row)
            OUT.write_text(json.dumps(data,indent=2,default=str),encoding='utf-8')
            print(name, json.dumps({'text':str(row.get('display_text') or '')[:450],
                                   'error':row.get('error'),'audit':row.get('audit_passed'),
                                   'shine':row.get('shine_ok')}),flush=True)
    finally:
        app.close()
        OUT.write_text(json.dumps(data,indent=2,default=str),encoding='utf-8')
        print('Evidence saved:',OUT,flush=True)


if __name__=='__main__':
    main()
