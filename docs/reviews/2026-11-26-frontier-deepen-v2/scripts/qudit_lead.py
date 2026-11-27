"""Show the qudit-dimension barren-plateau lead: Frontier entries (screen) and full Deepen receipts."""
import json, pathlib, sys
from cpu_llm.pipeline import Appliance

def main():
    out = pathlib.Path(sys.argv[1])
    with Appliance(namespace='quantum_computing') as app:
        r = app.ask('Frontier: barren plateaus.', frontier={'topic': 'barren plateaus', 'screen': True})['frontier']
        picked = [h for h in r['hypotheses'] if 'qudit' in h['text'].casefold() and h['text'].startswith('Gains')]
        result = []
        for h in picked:
            d = app.ask('Deepen this hypothesis.', deepen={'hypothesis': h, 'novelty': True})
            result.append(dict(frontier_entry=h, deepen=d.get('deepen'), reply=d['reply']['text']))
        out.write_text(json.dumps(result, indent=1, ensure_ascii=False))
        for item in result:
            h, dp = item['frontier_entry'], item['deepen']
            print('\n=====', h['text'])
            print('id', h['id'], '| scores', h['scores'], '| rank', r['hypotheses'].index(h) + 1, 'of', len(r['hypotheses']))
            for c in h['citations']:
                print('  cite', c['document_id'], '|', c['quote'])
            print('  falsification:', h['falsification_test'])
            print('  deepen:', dp['verdict'], dp['lead_status'], [l['status'] for l in dp['links']],
                  'composition', dp['composition']['status'], 'novelty', dp['novelty_review']['kb_status'])
            tp = dp['test_plan']
            print('  plan', tp['design'], '| types', tp.get('variable_types'), '| reason', tp.get('design_reason'))
            for s in tp['steps']:
                print('   -', s)
            print('   fails if:', tp.get('fails_if'))
            print('   controls:', tp.get('controls'))
            print('   suggested:', {k: [i['document_id'] for i in v] for k, v in tp.get('suggested_procedures', {}).items()})
            for l in dp['links']:
                for c in l['support'][:2]:
                    print('   link', l['source'], '->', l['target'], '|', c['document_id'], c.get('endpoint_match'), '|', c['quote'][:220])

if __name__ == '__main__':
    main()
