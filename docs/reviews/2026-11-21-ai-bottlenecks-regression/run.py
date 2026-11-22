"""Live regression on the recorded AI-bottleneck snapshot; never re-ingest."""
import hashlib
import json
import os
from pathlib import Path
from time import perf_counter

from cpu_llm.access import CallerContext
from cpu_llm.pipeline import Appliance


def save(path, data):
    path.write_text(json.dumps(data, indent=2, ensure_ascii=False, default=str), encoding='utf-8')


def main():
    root = Path.cwd()
    baseline_dir = root / 'build/ai-bottlenecks-fixed-run'
    baseline = json.loads((baseline_dir / 'results.json').read_text(encoding='utf-8'))
    focused = json.loads((baseline_dir / 'focused.json').read_text(encoding='utf-8'))
    corpus = dict(json.loads((baseline_dir / 'corpus.json').read_text(encoding='utf-8')))
    out = root / 'build/ai-bottlenecks-regression-20261121'
    out.mkdir(exist_ok=True)
    if (out / 'results.json').exists():
        raise RuntimeError('Preserve the existing run; choose a fresh output directory.')
    files = ['src/cpu_llm/' + name + '.py' for name in
             ('deepen', 'deepen_review', 'frontier', 'hypothesis_routes', 'pipeline')]
    hashes = {p: hashlib.sha256((root / p).read_bytes()).hexdigest() for p in files}
    os.environ['FRONTIER_PARSER'] = str(root / 'build/ai-bottlenecks-nlp/en_core_web_sm/en_core_web_sm-3.8.0')
    os.chdir(out)
    result = dict(baseline_revision=baseline['revision'], implementation_sha256=hashes,
                  snapshot=baseline['snapshot'], documents=64, chunks=1054, runs=[])
    transcripts = ['# AI-bottlenecks regression: exact prompts and responses']
    with Appliance(namespace=baseline['namespace'], small_talk=False, prompt_backend='rules',
                   dsn='postgresql://postgres@127.0.0.1:55433/cpullm_inference_live') as app:
        rows, _ = app.index.strict_source_rows(None, as_of=baseline['snapshot'])
        assert {r['document_id']: r['chunk_text'] for r in rows} == corpus, 'Recorded source corpus changed.'
        result['corpus_exact_match'] = True
        print('CORPUS', len(rows), 'chunks match baseline', flush=True)
        cases = [(r, None) for r in baseline['runs']] + [(focused, CallerContext(
            tenant_id=app.tenant_id, caller_id='regression-focused', request_id='focused',
            allowed_sources=frozenset('arxiv-' + s.replace('.', '-') + '-p' for s in focused['sources'])))]
        for number, (old, caller) in enumerate(cases, 1):
            previous = old['response']['frontier']
            prompt = old['prompt']
            started = perf_counter()
            response = app.ask(prompt, caller=caller, as_of=baseline['snapshot'], session_id=f'case-{number}',
                frontier=dict(topic=previous['topic'], limits=dict(max_seconds=120), deepen_top=5))
            current = response.get('frontier', {})
            signature = lambda r: [(h['id'], h['text'], h['scores']) for h in r.get('hypotheses', [])]
            checks = dict(candidate_ids_texts_scores_and_order_unchanged=signature(previous) == signature(current),
                result_count_unchanged=len(previous['hypotheses']) == len(current.get('hypotheses', [])),
                search_complete=not current.get('incomplete', True),
                hypotheses_remain_unverified=all(h.get('claim_status') == 'UNVERIFIED_HYPOTHESIS'
                    and h.get('promotion') == 'blocked' for h in current.get('hypotheses', [])))
            item = dict(number=number, prompt=prompt, topic=previous['topic'], baseline_count=len(previous['hypotheses']),
                count=len(current.get('hypotheses', [])), frontier_seconds=round(perf_counter()-started, 3),
                checks=checks, response=response, deepen_runs=[])
            transcripts += [f'## Case {number}: Frontier prompt', prompt, '### Frontier response', response['reply']['text']]
            print('FRONTIER', number, item['count'], checks, flush=True)
            for index, hypothesis in enumerate(current.get('hypotheses', [])[:3], 1):
                session = f'case-{number}-idea-{index}'
                started = perf_counter()
                deepen = app.ask('Examine this proposal.', caller=caller, as_of=baseline['snapshot'], session_id=session,
                                 deepen=dict(hypothesis=hypothesis, novelty=True))
                receipt = deepen.get('deepen', {})
                check = dict(complete=not receipt.get('incomplete', True),
                    unverified=receipt.get('claim_status') == 'UNVERIFIED_HYPOTHESIS' and receipt.get('promotion') == 'blocked',
                    no_kb_write=receipt.get('index_write') is False,
                    no_external_review=receipt.get('novelty_review', {}).get('external_status') == 'not_requested',
                    experiment_not_executed=receipt.get('test_plan', {}).get('executed') is False)
                detail = dict(index=index, hypothesis=hypothesis['text'], seconds=round(perf_counter()-started, 3),
                              checks=check, response=deepen)
                item['deepen_runs'].append(detail)
                transcripts += [f'### Deepen idea {index}: {hypothesis["text"]}', deepen['reply']['text']]
                print('DEEPEN', number, index, receipt.get('verdict'), receipt.get('composition', {}).get('status'), flush=True)
                if number == 4 and index == 1:
                    detail['followups'] = []
                    for turn in range(2):
                        follow = app.ask('Go deeper.', caller=caller, as_of=baseline['snapshot'], session_id=session)
                        detail['followups'].append(follow)
                        transcripts += [f'### Follow-up {turn+1}: Go deeper', follow['reply']['text']]
            result['runs'].append(item)
            save(out / f'case-{number}.json', item)
            save(out / 'partial-results.json', result)
        # The known semantic collision must stay visible, with a review warning.
        memory = result['runs'][2]['deepen_runs'][0]['response']['deepen']
        result['memory_bridge_flagged'] = bool(memory['composition']['bridges']) and memory['composition']['status'] == 'requires_review'
        focused_detail = result['runs'][3]['deepen_runs'][0]
        followups = [r['deepen']['progress'] for r in focused_detail['followups']]
        result['followup_focus_distinct'] = len({p['focus']['id'] for p in followups}) == 2
        result['followups_report_no_new_source_evidence'] = all(p['new_source_evidence'] is False for p in followups)
        result['source_files_unchanged_during_run'] = hashes == {
            p: hashlib.sha256((root / p).read_bytes()).hexdigest() for p in files}
        result['regression_passed'] = all(v for item in result['runs'] for v in item['checks'].values()) and all(
            v for item in result['runs'] for d in item['deepen_runs'] for v in d['checks'].values()) and all(
                result[k] for k in ('memory_bridge_flagged', 'followup_focus_distinct',
                                   'followups_report_no_new_source_evidence', 'source_files_unchanged_during_run'))
        save(out / 'results.json', result)
        (out / 'responses.md').write_text('\n\n'.join(transcripts), encoding='utf-8')
        print('FINAL', result['regression_passed'], flush=True)
        if not result['regression_passed']:
            raise SystemExit('Inspect the failed regression checks; raw outputs have been preserved.')


if __name__ == '__main__':
    main()
