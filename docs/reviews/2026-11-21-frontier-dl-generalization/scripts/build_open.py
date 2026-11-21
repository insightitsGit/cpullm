"""Build an open-problem corpus: full text for CC BY / BY-SA papers, abstracts otherwise. No holdout.

usage: build_open.py meta.json ids.txt textdir outdir "Corpus title" fetch-date
"""
import json, re, sys, pathlib, unicodedata
meta = json.load(open(sys.argv[1]))
ids = open(sys.argv[2]).read().split()
textdir, out, title, fetched = pathlib.Path(sys.argv[3]), pathlib.Path(sys.argv[4]), sys.argv[5], sys.argv[6]
out.mkdir(parents=True, exist_ok=True)
FULL_OK = ('/by/', '/by-sa/', 'publicdomain')
def clean(text):
    text = unicodedata.normalize('NFKC', text)
    text = ''.join(ch for ch in text if ch in '\n\t' or unicodedata.category(ch)[0] != 'C')
    text = re.sub(r'\$\\times\$', 'x', text)
    text = re.sub(r'\$([^$]*)\$', lambda m: re.sub(r'[\\{}_^]', '', m[1]), text)
    return ' '.join(text.split())
rows = []
for pid in ids:
    m = meta[pid]
    full = textdir / f'{pid}.txt'
    use_full = bool(m['licence']) and any(t in m['licence'] for t in FULL_OK) and full.exists() and full.stat().st_size > 1000
    paragraphs = full.read_text().split('\n\n') if use_full else [m['abstract']]
    kept = [p for p in (clean(p) for p in paragraphs) if len(p) >= 40]
    name = 'arxiv-' + pid.replace('.', '-')
    (out / f'{name}.md').write_text(f'# {clean(m["title"])}\n\n' + '\n\n'.join(kept) + '\n')
    rows.append((name, clean(m['title']), pid, m['date'], m['licence'], 'full text (before references, capped)' if use_full else 'abstract only'))
src = [f'# {title}: sources', '',
       f'Each file holds one arXiv paper, fetched from arXiv on {fetched}. Papers released under CC BY 4.0 or CC BY-SA 4.0 '
       'contribute body text (pypdf extraction before the references, capped, NFKC-normalized). All other papers contribute '
       'only their abstract, which arXiv releases as CC0 1.0 metadata (https://info.arxiv.org/help/license/index.html). '
       'Copyright in each paper remains with its authors; see the URL for attribution.', '',
       '| File | Title | URL | Date | Licence | Content used |', '|---|---|---|---|---|---|']
for name, t, pid, date, lic, used in rows:
    src.append(f'| `{name}.md` | {t.replace("|", "/")} | https://arxiv.org/abs/{pid} | {date} | {lic} | {used} |')
full_n = sum(r[5].startswith('full') for r in rows)
src += ['', f'{len(rows)} documents: {full_n} full text, {len(rows) - full_n} abstract only.']
(out / 'SOURCES.md').write_text('\n'.join(src) + '\n')
print(len(rows), 'documents', full_n, 'full text')
