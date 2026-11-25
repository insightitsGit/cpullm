"""Before/after evaluation for Frontier/Deepen v2 on the four evaluation namespaces.

usage: eval_v2.py outdir label [--screen]
Runs every prompt once with default options (and once with frontier={"screen": True} when --screen is given), and
Deepen on fixed hypotheses. Artefact share is measured with a fixed regex in this script, independent of the code
under test.
"""
import json, pathlib, re, sys, time
from cpu_llm.pipeline import Appliance

RUNS = {
    'ai_bottlenecks_frontier': ['AI bottlenecks', 'AI compute cost', 'AI energy bottlenecks', 'memory bandwidth bottlenecks', 'training data supply'],
    'dl_generalization_frontier': ['deep learning generalization', 'grokking', 'benign overfitting', 'implicit bias of gradient descent', 'generalization of overparameterized networks'],
    'consciousness_frontier': ['integrated information theory', 'global workspace theory', 'hard problem of consciousness', 'phenomenal consciousness', 'illusionism'],
    'quantum_computing': ['quantum error correction', 'fault-tolerant quantum computation', 'surface code decoders', 'barren plateaus', 'quantum advantage', 'error mitigation', 'two-level systems', 'qubit coherence', 'magic state distillation', 'correlated errors', 'leakage', 'quantum LDPC codes'],
}
DEEPEN = {
    'quantum_computing': [
        'Cosmic rays may reduce the error threshold through correlated errors.',
        'Leakage may increase logical error rates through correlated errors.',
        'reset may reduce Z error of output qubit through leakage induced long time correlated errors.',
        'mid - circuit measurements may reduce exponential scaling for gradient free optimizers through barren plateaus.',
        'chemical initialization and mid - circuit measurements may jointly constrain barren plateaus.',
        'low weight Pauli operators and samples may jointly constrain error mitigation.',
        'rapid distillation speed may increase error of circuit outcome through discarded magic states.',
        'Two-level system defects may reduce qubit coherence through dielectric loss.',
        'Error mitigation cost may increase exponentially with circuit size.',
        'Quantum LDPC codes may reduce the overhead of fault-tolerant quantum computation.',
        'Noise may remove quantum advantage through classical simulation of random circuits.',
    ],
    'dl_generalization_frontier': ['Low weight decay may increase generalization through the grokking phase.'],
}
ARTEFACT = re.compile(r"(?:^|\s)(?:[A-Z]|[IVX]+|\d+(?:\.\d+)*)\.\s+[A-Z]|\b[A-Z]\.\s?[A-Z][a-z]+|[a-z]{3,}(?:ofthe|tothe|bestof|ofour|ofnoisy)|"
                      r"\b(?:definition|issues|Recent (?:experiments|advances)|less than \d|majority of|Eliya|Nachmani|Dae - Young)\b")


def artefact(h):
    return any(ARTEFACT.search(t) for t in h['anchors'] + h.get('via', []))


def main():
    out, label, screen = pathlib.Path(sys.argv[1]), sys.argv[2], '--screen' in sys.argv
    out.mkdir(parents=True, exist_ok=True)
    summary = dict(label=label, frontier=[], deepen=[])
    for namespace, topics in RUNS.items():
        with Appliance(namespace=namespace) as app:
            for topic in topics:
                for mode in (['default', 'screen'] if screen else ['default']):
                    t0 = time.perf_counter()
                    reply = app.ask(f'Frontier: {topic}.', frontier={'topic': topic, 'screen': True} if mode == 'screen' else None)
                    seconds = round(time.perf_counter() - t0, 2)
                    r = reply.get('frontier') or {}
                    hyps = r.get('hypotheses', [])
                    checks = [h['check'] for h in hyps if h.get('check')]
                    row = dict(namespace=namespace, topic=topic, mode=mode, seconds=seconds, status=r.get('status'),
                               returned=len(hyps), artefact_entries=sum(artefact(h) for h in hyps),
                               ids=[h['id'] for h in hyps], texts=[h['text'] for h in hyps],
                               verdicts=[c.get('verdict') for c in checks],
                               lead_status=[c.get('lead_status') for c in checks],
                               incomplete=r.get('incomplete'), stop_reason=r.get('stop_reason'),
                               rejected=r.get('candidates_rejected'), topic_match=r.get('topic_match'),
                               screen=r.get('screen'))
                    summary['frontier'].append(row)
                    print(label, namespace, topic, mode, row['returned'], 'artefacts', row['artefact_entries'],
                          row['verdicts'], row['lead_status'], seconds, flush=True)
            for text in DEEPEN.get(namespace, []):
                t0 = time.perf_counter()
                reply = app.ask('Deepen this hypothesis.', deepen={'hypothesis': text, 'novelty': True})
                r = reply.get('deepen') or {}
                plan = r.get('test_plan') or {}
                row = dict(namespace=namespace, text=text, answer_status=reply['answer_status'],
                           verdict=r.get('verdict'), lead_status=r.get('lead_status'),
                           links=[l.get('status') for l in r.get('links', [])],
                           composition=(r.get('composition') or {}).get('status'), design=plan.get('design'),
                           blocked_design=plan.get('blocked_design'), variable_types=plan.get('variable_types'),
                           controls=[c.get('term') for c in r.get('confounders', [])],
                           seconds=round(time.perf_counter() - t0, 2))
                summary['deepen'].append(row)
                print(label, 'deepen |', text, '|', row['answer_status'], row['verdict'], row['lead_status'],
                      row['design'], row['controls'], flush=True)
    (out / f'{label}.json').write_text(json.dumps(summary, indent=1, ensure_ascii=False))


if __name__ == '__main__':
    main()
