"""Deepen open problems rephrased in the Frontier forms. usage: deepen_open.py outdir namespace"""
import json, pathlib, sys, time
from cpu_llm.pipeline import Appliance
PROBLEMS = [
    'Cosmic rays may reduce the error threshold through correlated errors.',
    'Noise may reduce quantum advantage through classical simulation.',
    'Barren plateaus may constrain variational quantum algorithms through classical simulability.',
    'Circuit size may increase error mitigation cost through sampling overhead.',
    'Quantum LDPC codes may reduce qubit overhead through encoding rate.',
    'Quantum LDPC codes may increase decoder complexity through long-range connectivity.',
    'Leakage may increase logical error rates through correlated errors.',
    'Two-level system defects may reduce qubit coherence through dielectric loss.',
]
def main():
    out, ns = pathlib.Path(sys.argv[1]), sys.argv[2]
    with Appliance(namespace=ns) as app:
        for text in PROBLEMS:
            t0 = time.perf_counter()
            reply = app.ask('Deepen this hypothesis.', deepen={'hypothesis': text, 'novelty': True})
            r = reply.get('deepen') or {}
            slug = ''.join(c if c.isalnum() else '-' for c in text.casefold()).strip('-')[:60]
            (out / f'open_problem-{slug}.json').write_text(json.dumps(dict(kind='open_problem', hypothesis=text,
                seconds=round(time.perf_counter() - t0, 2), answer_status=reply['answer_status'], deepen=r,
                reply=reply['reply']['text']), indent=1, ensure_ascii=False))
            print('|', text, '|', reply['answer_status'], r.get('verdict'), [l.get('status') for l in r.get('links', [])],
                  (r.get('composition') or {}).get('status'), flush=True)


if __name__ == '__main__':
    main()
