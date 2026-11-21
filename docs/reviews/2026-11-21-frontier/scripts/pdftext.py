"""Extract body text (before References), dehyphenate, keep prose lines, cap length."""
import json, re, sys, pathlib
from pypdf import PdfReader
src, dst, cap = pathlib.Path(sys.argv[1]), pathlib.Path(sys.argv[2]), int(sys.argv[3])
dst.mkdir(exist_ok=True)
stats = {}
for pdf in sorted(src.glob('*.pdf')):
    try:
        reader = PdfReader(str(pdf))
        pages = []
        for page in reader.pages[:40]:
            pages.append(page.extract_text() or '')
    except Exception as exc:
        stats[pdf.stem] = f'error {exc}'; continue
    text = '\n'.join(pages)
    cut = re.search(r'\n\s*(?:\d+\s*)?(?:References|Bibliography|REFERENCES|Acknowledg(?:e)?ments)\s*\n', text)
    if cut and cut.start() > 2000:
        text = text[:cut.start()]
    text = re.sub(r'-\n(?=[a-z])', '', text)
    lines = []
    for line in text.split('\n'):
        line = line.strip()
        words = re.findall(r'[A-Za-z]{2,}', line)
        if len(words) < 4 or sum(c.isdigit() for c in line) > len(line) * 0.3:
            lines.append('\n')
            continue
        lines.append(line)
    body = re.sub(r'\s*\n\s*\n\s*', '\n\n', ' '.join(lines).replace(' \n ', '\n\n'))
    paragraphs = [' '.join(p.split()) for p in body.split('\n\n')]
    paragraphs = [p for p in paragraphs if len(p) >= 200 and not re.search(r'arXiv:\d|https?://|@', p[:80])]
    out, size = [], 0
    for p in paragraphs:
        if size + len(p) > cap:
            break
        out.append(p); size += len(p)
    (dst / f'{pdf.stem}.txt').write_text('\n\n'.join(out))
    stats[pdf.stem] = dict(paragraphs=len(out), chars=size, pages=len(reader.pages))
json.dump(stats, open(dst / 'stats.json', 'w'), indent=1)
for k, v in stats.items(): print(k, v)
