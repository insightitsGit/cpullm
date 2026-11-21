"""usage: e2e_open.py repo outdir fixtures-subdir namespace 'prompt|prompt'"""
import json, pathlib, resource, sys, time, tracemalloc
from cpu_llm.pipeline import Appliance
from cpu_llm.documents import open_source

def main():
    repo = pathlib.Path(sys.argv[1]); out = pathlib.Path(sys.argv[2]); out.mkdir(parents=True, exist_ok=True)
    fixtures = repo / sys.argv[3]
    files = sorted(fixtures.glob('arxiv-*.md'))
    prompts = sys.argv[5].split('|')
    log = dict(namespace=sys.argv[4], documents=len(files), runs=[])
    with Appliance(namespace=sys.argv[4]) as app:
        started = time.perf_counter()
        for path in files:
            app.ingest(path)
        log['ingest_seconds'] = round(time.perf_counter() - started, 2)
        rows, _ = app.index.strict_source_rows(None)
        log['chunks'] = len(rows)
        for prompt in prompts:
            for run in range(1, 4):
                tracemalloc.start()
                t0 = time.perf_counter()
                result = app.ask(prompt)
                seconds = time.perf_counter() - t0
                _, peak = tracemalloc.get_traced_memory()
                tracemalloc.stop()
                receipt = result['frontier']
                name = prompt.removeprefix('Frontier: ').rstrip('.').replace(' ', '-').lower()
                (out / f'raw-{name}-run{run}.json').write_text(json.dumps(dict(
                    prompt=prompt, run=run, wall_seconds=round(seconds, 3), python_peak_bytes=peak,
                    answer_status=result['answer_status'], routing=result.get('routing'), frontier=receipt,
                    reply=result['reply']['text']), indent=1, ensure_ascii=False))
                log['runs'].append(dict(prompt=prompt, run=run, wall_seconds=round(seconds, 3), python_peak_mb=round(peak / 2**20, 1),
                                        status=receipt['status'], returned=len(receipt['hypotheses']),
                                        generated=receipt['candidates_generated'], passed=receipt['candidates_passed'],
                                        incomplete=receipt['incomplete'], budget_used=receipt['budget_used'],
                                        ids=[h['id'] for h in receipt['hypotheses']]))
                print(prompt, run, receipt['status'], len(receipt['hypotheses']), receipt['candidates_generated'],
                      receipt['candidates_passed'], round(seconds, 2), flush=True)
    log['max_rss_mb'] = round(resource.getrusage(resource.RUSAGE_SELF).ru_maxrss / 1024, 1)
    (out / 'runs.json').write_text(json.dumps(log, indent=1))


if __name__ == '__main__':
    main()
