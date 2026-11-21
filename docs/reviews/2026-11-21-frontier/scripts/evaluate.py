import json, pathlib, sys, statistics
review = pathlib.Path(sys.argv[1]); holdout = json.load(open(sys.argv[2]))
runs = json.load(open(review / 'runs.json'))
def match(text, groups):
    low = text.casefold()
    return all(any(term in low for term in group) for group in groups)
prompts = list(dict.fromkeys(r['prompt'] for r in runs['runs']))
summary = dict(prompts={}, holdout={})
all_hyps = {}
for prompt in prompts:
    name = prompt.removeprefix('Frontier: ').rstrip('.').replace(' ', '-').lower()
    raws = [json.load(open(review / f'raw-{name}-run{i}.json')) for i in (1, 2, 3)]
    ids = [[h['id'] for h in r['frontier']['hypotheses']] for r in raws]
    texts = [[h['text'] for h in r['frontier']['hypotheses']] for r in raws]
    f = raws[0]['frontier']
    summary['prompts'][prompt] = dict(
        status=f['status'], returned=len(f['hypotheses']), survivors=f.get('survivors'),
        generated=f['candidates_generated'], passed=f['candidates_passed'], rejected=f['candidates_rejected'],
        relation_edges=f['relation_edges'], scoped_edges=f['scoped_edges'], focus=f['focus_terms'],
        focus_fallback=f.get('focus_fallback', False), budget_used=[r['frontier']['budget_used'] for r in raws],
        incomplete=[r['frontier']['incomplete'] for r in raws],
        wall_seconds=[r['wall_seconds'] for r in raws], python_peak_mb=[round(r['python_peak_bytes'] / 2**20, 1) for r in raws],
        identical_ids_across_runs=ids[0] == ids[1] == ids[2], identical_text_across_runs=texts[0] == texts[1] == texts[2],
        top10=[dict(text=h['text'], scores=h['scores'], sources=h['source_ids'], pattern=h['pattern'],
                    relation=h['relation'], quotes=[c['quote'] for c in h['citations']],
                    falsification=h['falsification_test'], assumptions=h['assumptions'])
               for h in f['hypotheses'][:10]])
    for h in f['hypotheses']:
        all_hyps.setdefault(h['id'], dict(h, prompts=[]))['prompts'].append(prompt)
for key, item in holdout.items():
    full = [h for h in all_hyps.values() if match(h['text'], item['criteria']['full'])]
    partial = [h for h in all_hyps.values() if match(h['text'], item['criteria']['partial']) and h not in full]
    summary['holdout'][key] = dict(finding=item['finding'], full=[(h['text'], h['prompts']) for h in full],
                                   partial=[(h['text'], h['prompts']) for h in partial])
summary['distinct_hypotheses'] = len(all_hyps)
summary['corpus'] = {k: v for k, v in runs.items() if k != 'runs'}
json.dump(summary, open(review / 'evaluation.json', 'w'), indent=1, ensure_ascii=False)
for p, s in summary['prompts'].items():
    print(p, s['status'], s['returned'], s['generated'], s['passed'], s['identical_ids_across_runs'], s['wall_seconds'], s['python_peak_mb'], s['focus'], s['focus_fallback'])
for k, v in summary['holdout'].items():
    print(k, 'full', len(v['full']), 'partial', len(v['partial']))
    for t, ps in v['full'][:4]: print('   F', t)
    for t, ps in v['partial'][:3]: print('   P', t)
print('distinct', len(all_hyps))
