"""Frontier on quantum computing open problems, then Deepen (with novelty review) on the leading seeds and on
open problems phrased as hypotheses.

usage: run_qc.py outdir namespace
"""
import json, pathlib, resource, sys, time
from cpu_llm.pipeline import Appliance

TOPICS = ['quantum error correction', 'fault-tolerant quantum computation', 'surface code decoders',
          'barren plateaus', 'quantum advantage', 'error mitigation', 'two-level systems', 'qubit coherence',
          'magic state distillation', 'correlated errors', 'leakage', 'quantum LDPC codes']
OPEN_PROBLEMS = [
    'Correlated errors from cosmic rays may limit the threshold of surface code error correction.',
    'Two-level system defects may reduce qubit coherence through dielectric loss.',
    'Noise may remove quantum advantage through classical simulation of random circuits.',
    'Barren plateaus may imply classical simulability of variational quantum algorithms.',
    'Leakage may increase logical error rates through correlated errors.',
    'Error mitigation cost may increase exponentially with circuit size.',
    'Quantum LDPC codes may reduce the overhead of fault-tolerant quantum computation.',
]
SEEDS_PER_TOPIC = 3


def slug(text):
    return ''.join(ch if ch.isalnum() else '-' for ch in text.casefold()).strip('-')[:60]


def summary(receipt):
    return dict(verdict=receipt.get('verdict'), links=[l.get('status') for l in receipt.get('links', [])],
                composition=(receipt.get('composition') or {}).get('status'),
                bridges=len((receipt.get('composition') or {}).get('bridges') or []),
                novelty=(receipt.get('novelty_review') or {}).get('kb_status'))


def main():
    out, namespace = pathlib.Path(sys.argv[1]), sys.argv[2]
    (out / 'frontier').mkdir(parents=True, exist_ok=True)
    (out / 'deepen').mkdir(parents=True, exist_ok=True)
    log = dict(namespace=namespace, frontier=[], deepen=[])
    with Appliance(namespace=namespace) as app:
        rows, _ = app.index.strict_source_rows(None)
        log['chunks'] = len(rows)
        seeds = []
        for topic in TOPICS:
            prompt = f'Frontier: {topic}.'
            t0 = time.perf_counter()
            result = app.ask(prompt)
            seconds = round(time.perf_counter() - t0, 2)
            receipt = result.get('frontier') or {}
            (out / 'frontier' / f'{slug(topic)}.json').write_text(json.dumps(dict(
                prompt=prompt, seconds=seconds, answer_status=result['answer_status'], frontier=receipt,
                reply=result['reply']['text']), indent=1, ensure_ascii=False))
            hyps = receipt.get('hypotheses', [])
            checks = [((h.get('check') or {}).get('verdict')) for h in hyps]
            log['frontier'].append(dict(topic=topic, seconds=seconds, status=receipt.get('status'),
                                        returned=len(hyps), generated=receipt.get('candidates_generated'),
                                        passed=receipt.get('candidates_passed'), incomplete=receipt.get('incomplete'),
                                        checks=[c for c in checks if c]))
            print('frontier', topic, receipt.get('status'), len(hyps), seconds, [c for c in checks if c], flush=True)
            picked = [h for h in hyps if (h.get('check') or {}).get('verdict') not in ('contested',)][:SEEDS_PER_TOPIC]
            seeds += [(topic, h) for h in picked]
        jobs = [('seed', topic, h) for topic, h in seeds] + [('open_problem', None, text) for text in OPEN_PROBLEMS]
        for kind, topic, hypothesis in jobs:
            text = hypothesis['text'] if isinstance(hypothesis, dict) else hypothesis
            t0 = time.perf_counter()
            reply = app.ask('Deepen this hypothesis.', deepen={'hypothesis': hypothesis, 'novelty': True})
            seconds = round(time.perf_counter() - t0, 2)
            receipt = reply.get('deepen') or {}
            (out / 'deepen' / f'{kind}-{slug(text)}.json').write_text(json.dumps(dict(
                kind=kind, topic=topic, hypothesis=hypothesis, seconds=seconds, answer_status=reply['answer_status'],
                deepen=receipt, reply=reply['reply']['text']), indent=1, ensure_ascii=False))
            row = dict(kind=kind, topic=topic, text=text, seconds=seconds, answer_status=reply['answer_status'],
                       **summary(receipt))
            log['deepen'].append(row)
            print('deepen', kind, '|', text, '|', row['verdict'], row['links'], row['composition'], row['novelty'],
                  seconds, flush=True)
    log['max_rss_mb'] = round(resource.getrusage(resource.RUSAGE_SELF).ru_maxrss / 1024, 1)
    (out / 'runs.json').write_text(json.dumps(log, indent=1))


if __name__ == '__main__':
    main()
