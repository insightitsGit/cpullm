"""Build docs/research/quantum-computing-leads.{json,md} from the recorded Frontier and Deepen runs.

Citations, scores, falsification tests and Deepen results are copied from the run files; the annotations below
(why, caveats, next steps, priority) are the reviewer's. usage: build_leads.py review-dir out-dir
"""
import glob, json, pathlib, sys

LEADS = [
    dict(id='QC-1', priority='high', title='Do barren-plateau mitigations also remove the exponential cost of gradient-free optimizers?',
         frontier=['mid - circuit measurements may reduce exponential scaling for gradient free optimizers',
                   'chemical initialization may reduce exponential scaling for gradient free optimizers',
                   'MPQC may reduce exponential scaling for gradient free optimizers'],
         why='Barren plateaus make even gradient-free optimizers scale exponentially (2011.12245). Three papers report '
             'mitigations for gradients. No paper in the knowledge base tests whether those mitigations also cut the '
             'shot cost of gradient-free optimizers.',
         caveats=['Barren-plateau-free models are often classically simulable (Cerezo et al., arXiv:2312.09121, not in this knowledge base); check whether each mitigated regime is.',
                  'Mitigations were shown for specific settings (chemistry VQE, thermal-state PQCs); results may not transfer.'],
         next_steps=['Search the literature for gradient-free optimizers combined with each mitigation.',
                     'Simulate 4–12 qubit circuits with and without each mitigation; measure cost-function variance and the shots a gradient-free optimizer (e.g. Nelder–Mead, COBYLA) needs to reach a fixed accuracy, versus qubit count.',
                     'Fit exponential vs polynomial scaling; the hypothesis fails if the shot count still grows exponentially with the mitigation.']),
    dict(id='QC-2', priority='medium', title='Do two barren-plateau mitigations combine (chemical initialization × mid-circuit measurements)?',
         frontier=['chemical initialization and mid - circuit measurements may jointly constrain barren plateaus'],
         why='Each mitigation is reported separately (2609.22729, 2406.14285); none of the 155 papers combines them. Deepen rated the composition conditional and proposed a 2×2 factorial.',
         caveats=['The same classical-simulability caveat as QC-1.', 'Interaction may be absent; a null result does not refute either effect alone.'],
         next_steps=['Run the 2×2 simulation: neither, each alone, both; measure gradient variance versus system size.',
                     'Predefine an effect threshold for "interaction".']),
    dict(id='QC-3', priority='medium', title='How much of the cosmic-ray penalty can correlation-aware decoding recover?',
         open_problem='Cosmic rays may reduce the error threshold through correlated errors.',
         why='Deepen marked this open problem contested: cosmic rays cause correlated errors at about 1/(10 min) '
             '(2402.03208), while accounting for correlated errors in decoding raises the threshold in concatenated '
             'codes (2407.16176). The conflict is partly a meaning slip ("taking into account" correlations), but it '
             'points at a quantitative question.',
         caveats=['This is a known research direction, not a new discovery.', 'Radiation events are bursts that can exceed what decoders can model.'],
         next_steps=['Review the literature on radiation-aware and correlation-aware decoders.',
                     'Simulate a surface code with injected radiation-like bursts; compare a standard decoder with one given the burst model.']),
    dict(id='QC-4', priority='medium', title='Is error mitigation useful only where classical simulation is already easy?',
         frontier=['low weight Pauli operators and samples may jointly constrain error mitigation'],
         why='Recoverable observables must be dominated by low-weight Pauli operators, which are easy to simulate classically '
             '(2607.25746), and mitigation needs superpolynomially many samples even at low depth (2210.11505). Together '
             'they suggest a squeeze: the regime where mitigation is cheap may overlap the regime where it is unnecessary.',
         caveats=['Both papers are about worst-case or asymptotic bounds; practical instances may fall outside them.', 'Likely discussed in the field already.'],
         next_steps=['Check whether a paper states the trade-off directly.',
                     'For a benchmark family, map observable weight versus mitigation sample cost versus classical simulation cost.']),
    dict(id='QC-5', priority='low', title='Distillation speed versus circuit error in magic-state factories',
         frontier=['rapid distillation speed may increase error of circuit outcome'],
         why='Too rapid distillation discards magic states (2407.07394); a faulty magic state causes a circuit error with probability equal to its infidelity (1905.06903).',
         caveats=['A speed/fidelity trade-off is known in outline; the chain mixes "discarded" with "faulty" states (composition requires review).'],
         next_steps=['Read 2407.07394 for how discarded states are handled; the link to output error may not hold if discarded states are never used.']),
    dict(id='QC-6', priority='low', title='Do radiation bursts correlate failures inside magic-state factories?',
         frontier=['Cosmic rays and faulty magic state may jointly drive correlated errors'],
         why='Cosmic rays cause correlated errors (2402.03208); faulty magic states cause circuit errors (1905.06903). '
             'If a burst hits a factory, many distilled states could fail together.',
         caveats=['Speculative; not checked with Deepen. The two sources study different systems.'],
         next_steps=['Run Deepen with the novelty review on this entry.', 'Search for radiation effects on distillation factories.']),
]
GAPS = ['Noise may reduce quantum advantage through classical simulation.',
        'Barren plateaus may constrain variational quantum algorithms through classical simulability.',
        'Circuit size may increase error mitigation cost through sampling overhead.',
        'Quantum LDPC codes may reduce qubit overhead through encoding rate.',
        'Quantum LDPC codes may increase decoder complexity through long-range connectivity.',
        'Two-level system defects may reduce qubit coherence through dielectric loss.']


def url(doc):
    stem = doc.removeprefix('arxiv-').rsplit('-p', 1)[0]
    return 'https://arxiv.org/abs/' + stem.replace('-', '.', 1) if stem[:4].isdigit() else 'https://arxiv.org/abs/' + stem.replace('_', '/').replace('-', '.')


def main():
    review, out = pathlib.Path(sys.argv[1]), pathlib.Path(sys.argv[2])
    entries = {}
    for f in sorted(glob.glob(str(review / 'frontier' / '*.json'))):
        d = json.loads(pathlib.Path(f).read_text())
        for rank, h in enumerate(d['frontier']['hypotheses'], 1):
            entries.setdefault(h['text'], (d['frontier']['topic'], rank, h))
    deepened = {}
    for f in glob.glob(str(review / 'deepen*' / '*.json')):
        d = json.loads(pathlib.Path(f).read_text())
        text = d['hypothesis']['text'] if isinstance(d['hypothesis'], dict) else d['hypothesis']
        deepened[text] = d['deepen']

    def deepen_summary(text):
        r = deepened.get(text)
        if not r:
            return None
        plan = r.get('test_plan') or {}
        return dict(verdict=r.get('verdict'), links=[l.get('status') for l in r.get('links', [])],
                    composition=(r.get('composition') or {}).get('status'),
                    novelty_kb=(r.get('novelty_review') or {}).get('kb_status'),
                    test_design=plan.get('design'), vary=plan.get('manipulate'), measure=plan.get('measure'),
                    fails_if=plan.get('fails_if'),
                    confounders=[c.get('term') for c in (r.get('confounders') or [])][:5])

    leads = []
    for lead in LEADS:
        lead = dict(lead, status='open', claim_status='UNVERIFIED_HYPOTHESIS', hypotheses=[])
        for prefix in lead.pop('frontier', []):
            text = next(t for t in entries if t.startswith(prefix))
            topic, rank, h = entries[text]
            lead['hypotheses'].append(dict(
                text=text, frontier_id=h['id'], topic=topic, rank=rank, scores=h['scores'],
                citations=[dict(document_id=c['document_id'], url=url(c['document_id']), quote=c['quote'])
                           for c in h['citations']],
                falsification_test=h.get('falsification_test'), deepen=deepen_summary(text)))
        if 'open_problem' in lead:
            text = lead.pop('open_problem')
            r = deepened[text]
            cites = [dict(document_id=e['document_id'], url=url(e['document_id']), quote=e['quote'])
                     for l in r.get('links', []) for e in (l.get('support') or [])[:1]]
            lead['hypotheses'].append(dict(text=text, source='open problem phrased for Deepen', citations=cites,
                                           deepen=deepen_summary(text)))
        leads.append(lead)
    data = dict(schema='research-leads-v1', domain='quantum computing', created='2026-11-25',
                knowledge_base=dict(namespace='quantum_computing', fixtures='tests/fixtures/quantum_computing',
                                    papers=155, full_text=58, chunks=3369),
                engine='cpu-llm 1.16.0 (main 17a1315), parser en_core_web_lg, encoder all-mpnet-base-v2',
                review='docs/reviews/2026-11-25-quantum-computing/report.md',
                note='Every lead is an UNVERIFIED_HYPOTHESIS. Novelty was checked only against this knowledge base.',
                leads=leads, coverage_gaps=[dict(hypothesis=g, deepen=deepen_summary(g)) for g in GAPS])
    (out / 'quantum-computing-leads.json').write_text(json.dumps(data, indent=1, ensure_ascii=False) + '\n')

    md = ['# Quantum computing research leads', '',
          'Created 2026-11-25 from a Frontier and Deepen run over 155 arXiv quant-ph papers '
          '([review](../reviews/2026-11-25-quantum-computing/report.md), machine-readable copy: '
          '[quantum-computing-leads.json](quantum-computing-leads.json)).', '',
          '**Every lead is an `UNVERIFIED_HYPOTHESIS`.** None solves an open problem. Novelty was checked only against '
          'the 155-paper knowledge base, not the wider literature. Update `status` (open, in progress, known in '
          'literature, supported, refuted) and add notes as research proceeds.', '',
          '| ID | Priority | Lead | Status |', '|---|---|---|---|']
    md += [f"| [{l['id']}](#{l['id'].lower()}) | {l['priority']} | {l['title']} | {l['status']} |" for l in leads]
    for l in leads:
        md += ['', f"## {l['id']}", '', f"**{l['title']}** · priority {l['priority']} · status {l['status']}", '',
               l['why'], '']
        for h in l['hypotheses']:
            where = f"Frontier `{h['frontier_id']}`, topic “{h['topic']}”, rank {h['rank']}" if 'frontier_id' in h else h['source']
            md += [f"- **Hypothesis:** {h['text']} ({where})"]
            if h.get('scores'):
                s = h['scores']
                md += [f"  - Scores: support {s['source_support']}, relevance {s['deductive_relevance']}, novelty {s['novelty']}"]
            for c in h['citations']:
                md += [f"  - [{c['document_id']}]({c['url']}): “{c['quote']}”"]
            dp = h.get('deepen')
            if dp:
                md += [f"  - Deepen: verdict `{dp['verdict']}`, links {dp['links']}, composition `{dp['composition']}`, "
                       f"knowledge-base novelty `{dp['novelty_kb']}`"]
                if dp.get('test_design'):
                    md += [f"  - Test plan ({dp['test_design']}): vary {dp['vary']}, measure {dp['measure']}. Fails if: {dp['fails_if']}"]
            else:
                md += ['  - Deepen: not run yet']
        md += ['', '**Caveats**', ''] + [f'- {c}' for c in l['caveats']]
        md += ['', '**Next steps**', ''] + [f'{i}. {s}' for i, s in enumerate(l['next_steps'], 1)]
    md += ['', '## Coverage gaps', '',
           'These open problems, phrased as hypotheses, found no usable evidence chain. The cause is thin coverage '
           '(most papers on them were abstracts only), not evidence against them. Adding full-text papers is the next step.', '']
    for g in data['coverage_gaps']:
        dp = g['deepen'] or {}
        md += [f"- {g['hypothesis']}: `{dp.get('verdict')}`, links {dp.get('links')}"]
    md += ['', '## Reproduce', '',
           'Ingest `tests/fixtures/quantum_computing` into a namespace, then pass a hypothesis back to Deepen:', '',
           '```python', 'app.ask("Deepen this.", deepen={"hypothesis": "<hypothesis text>", "novelty": True})', '```', '',
           'Regenerate this page with `docs/reviews/2026-11-25-quantum-computing/scripts/build_leads.py`.']
    (out / 'quantum-computing-leads.md').write_text('\n'.join(md) + '\n')
    print(len(leads), 'leads')


if __name__ == '__main__':
    main()
