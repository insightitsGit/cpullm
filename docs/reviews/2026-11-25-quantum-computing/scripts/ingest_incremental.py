"""Build and ingest each downloaded paper as soon as its fetch is finished.

usage: ingest_incremental.py workdir fixtures-dir namespace
A paper is ready when its abstract page exists and the next id's page exists too (so its PDF, if any, is complete),
or when the fetch has finished (workdir/FETCH_DONE). Loops until every id is ingested.
"""
import html, json, pathlib, re, sys, time, unicodedata
from pypdf import PdfReader
from cpu_llm.pipeline import Appliance

FULL_OK = ('/by/', '/by-sa/', 'publicdomain')
CAP = 60000


def meta(text):
    def tag(name):
        m = re.search(r'<meta name="%s" content="([^"]*)"' % name, text)
        return html.unescape(m[1]).strip() if m else None
    lic = re.search(r'href="(https?://(?:creativecommons\.org/[^"]+|arxiv\.org/licenses/[^"]+))"', text)
    return dict(title=tag('citation_title'), date=tag('citation_date'), abstract=tag('citation_abstract'),
                licence=lic[1] if lic else None)


def clean(text):
    text = unicodedata.normalize('NFKC', text)
    text = ''.join(ch for ch in text if ch in '\n\t' or unicodedata.category(ch)[0] != 'C')
    text = re.sub(r'\$\\times\$', 'x', text)
    text = re.sub(r'\$([^$]*)\$', lambda m: re.sub(r'[\\{}_^]', '', m[1]), text)
    return ' '.join(text.split())


def pdf_paragraphs(path):
    reader = PdfReader(str(path))
    text = '\n'.join((page.extract_text() or '') for page in reader.pages[:40])
    cut = re.search(r'\n\s*(?:\d+\s*)?(?:References|Bibliography|REFERENCES|Acknowledg(?:e)?ments)\s*\n', text)
    if cut and cut.start() > 2000:
        text = text[:cut.start()]
    text = re.sub(r'-\n(?=[a-z])', '', text)
    lines = []
    for line in text.split('\n'):
        line = line.strip()
        if len(re.findall(r'[A-Za-z]{2,}', line)) < 4 or sum(c.isdigit() for c in line) > len(line) * 0.3:
            lines.append('\n'); continue
        lines.append(line)
    body = re.sub(r'\s*\n\s*\n\s*', '\n\n', ' '.join(lines).replace(' \n ', '\n\n'))
    paragraphs = [' '.join(p.split()) for p in body.split('\n\n')]
    paragraphs = [p for p in paragraphs if len(p) >= 200 and not re.search(r'arXiv:\d|https?://|@', p[:80])]
    out, size = [], 0
    for p in paragraphs:
        if size + len(p) > CAP:
            break
        out.append(p); size += len(p)
    return out


def main():
    work, fixtures, namespace = pathlib.Path(sys.argv[1]), pathlib.Path(sys.argv[2]), sys.argv[3]
    fixtures.mkdir(parents=True, exist_ok=True)
    ids = (work / 'ids.txt').read_text().split()
    state_path = work / 'ingested.json'
    state = json.loads(state_path.read_text()) if state_path.exists() else {}
    safe = lambda pid: pid.replace('/', '_')
    with Appliance(namespace=namespace) as app:
        while True:
            done = (work / 'FETCH_DONE').exists()
            for i, pid in enumerate(ids):
                if pid in state:
                    continue
                page = work / 'raw' / f'{safe(pid)}.html'
                nxt = work / 'raw' / f'{safe(ids[i + 1])}.html' if i + 1 < len(ids) else None
                if done and not page.exists():
                    state[pid] = dict(skipped='not fetched'); continue
                if not page.exists() or not (done or (nxt and nxt.exists())):
                    continue
                m = meta(page.read_text(errors='replace'))
                if not m['abstract']:
                    state[pid] = dict(skipped='no abstract'); continue
                pdf = work / 'pdf' / f'{safe(pid)}.pdf'
                full = bool(m['licence']) and any(t in m['licence'] for t in FULL_OK) and pdf.exists()
                paragraphs = []
                if full:
                    try:
                        paragraphs = pdf_paragraphs(pdf)
                    except Exception as exc:
                        print('pdf error', pid, exc, flush=True)
                full = full and sum(map(len, paragraphs)) > 1000
                kept = [p for p in (clean(p) for p in (paragraphs if full else [m['abstract']])) if len(p) >= 40]
                name = 'arxiv-' + safe(pid).replace('.', '-')
                path = fixtures / f'{name}.md'
                path.write_text(f'# {clean(m["title"])}\n\n' + '\n\n'.join(kept) + '\n')
                started = time.perf_counter()
                app.ingest(path)
                state[pid] = dict(name=name, title=clean(m['title']), date=m['date'], licence=m['licence'],
                                  used='full text (before references, capped)' if full else 'abstract only',
                                  seconds=round(time.perf_counter() - started, 2))
                state_path.write_text(json.dumps(state, indent=1))
                print(len(state), pid, state[pid]['used'], state[pid]['seconds'], 's', flush=True)
            if done and all(p in state for p in ids):
                break
            time.sleep(10)
    print('finished', len(state), flush=True)


if __name__ == '__main__':
    main()
