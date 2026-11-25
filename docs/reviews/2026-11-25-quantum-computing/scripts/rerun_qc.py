"""Corrected run: QEC with a 120 s budget, clearer TLS topics, and Deepen on curated topic-specific entries
from anywhere in each list of 50 (not only the top 3). usage: rerun_qc.py outdir namespace"""
import glob, json, pathlib, re, sys, time
from cpu_llm.pipeline import Appliance

TOPICS = [('quantum error correction', {'limits': {'max_seconds': 120}}), ('two-level system defects', {}),
          ('dielectric loss', {}), ('quasiparticles', {})]
JUNK = re.compile(r"\b[A-Z]\. [A-Z][a-z]+|Tothebest|\bdefinition\b|Implications for|^[A-Z]\.|\bet al\b|\bFig|\bSec\b|"
                  r"\bTable\b|latter|issues|\bspace\b|\bparticles\b|knowledge\b|theavailability|Recent (?:experiments|advances)|"
                  r"former|line of work|research\b|Eliya|less than \d|\bBin\b|\bKT\b|Devised|\bEMRE\b|majority of error")
PER_TOPIC = 4


def slug(text):
    return ''.join(c if c.isalnum() else '-' for c in text.casefold()).strip('-')[:60]


def curate(files):
    entries, topics_of = [], {}
    for f in files:
        d = json.loads(pathlib.Path(f).read_text())
        for h in d['frontier']['hypotheses']:
            topics_of.setdefault(h['text'], set()).add(d['frontier']['topic'])
            entries.append((d['frontier']['topic'], h))
    picked, used = [], set()
    by_topic = {}
    for topic, h in entries:
        terms = ' '.join(h['anchors'] + h.get('via', []))
        if (len(topics_of[h['text']]) > 1 or JUNK.search(terms) or h['text'] in used
                or (h.get('check') or {}).get('verdict') == 'contested'):
            continue
        used.add(h['text'])
        by_topic.setdefault(topic, []).append(h)
    for topic, hs in by_topic.items():
        hs.sort(key=lambda h: -(0.6 * h['scores']['deductive_relevance'] + 0.4 * h['scores']['novelty']))
        picked += [(topic, h) for h in hs[:PER_TOPIC]]
    return picked


def main():
    out, ns = pathlib.Path(sys.argv[1]), sys.argv[2]
    (out / 'frontier').mkdir(parents=True, exist_ok=True)
    (out / 'deepen-curated').mkdir(parents=True, exist_ok=True)
    log = dict(frontier=[], deepen=[])
    with Appliance(namespace=ns) as app:
        for topic, options in TOPICS:
            t0 = time.perf_counter()
            result = app.ask(f'Frontier: {topic}.', frontier=dict(options, topic=topic) if options else None)
            r = result.get('frontier') or {}
            seconds = round(time.perf_counter() - t0, 2)
            (out / 'frontier' / f'{slug(topic)}.json').write_text(json.dumps(dict(
                prompt=f'Frontier: {topic}.', options=options, seconds=seconds, answer_status=result['answer_status'],
                frontier=r, reply=result['reply']['text']), indent=1, ensure_ascii=False))
            checks = [(h.get('check') or {}).get('verdict') for h in r.get('hypotheses', []) if h.get('check')]
            log['frontier'].append(dict(topic=topic, seconds=seconds, returned=len(r.get('hypotheses', [])),
                                        incomplete=r.get('incomplete'), stop_reason=r.get('stop_reason'), checks=checks))
            print('frontier', topic, len(r.get('hypotheses', [])), seconds, r.get('stop_reason'), checks, flush=True)
        for topic, h in curate(sorted(glob.glob(str(out / 'frontier' / '*.json')))):
            t0 = time.perf_counter()
            reply = app.ask('Deepen this hypothesis.', deepen={'hypothesis': h, 'novelty': True})
            r = reply.get('deepen') or {}
            row = dict(topic=topic, text=h['text'], scores=h['scores'], seconds=round(time.perf_counter() - t0, 2),
                       verdict=r.get('verdict'), links=[l.get('status') for l in r.get('links', [])],
                       composition=(r.get('composition') or {}).get('status'),
                       novelty=(r.get('novelty_review') or {}).get('kb_status'))
            log['deepen'].append(row)
            (out / 'deepen-curated' / f'{slug(h["text"])}.json').write_text(json.dumps(dict(
                topic=topic, hypothesis=h, answer_status=reply['answer_status'], deepen=r, reply=reply['reply']['text']),
                indent=1, ensure_ascii=False))
            print('deepen', topic, '|', h['text'], '|', row['verdict'], row['links'], row['composition'], row['novelty'],
                  flush=True)
    (out / 'rerun.json').write_text(json.dumps(log, indent=1))


if __name__ == '__main__':
    main()
