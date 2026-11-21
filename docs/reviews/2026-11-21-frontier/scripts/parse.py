import html, json, re, sys, pathlib
out = {}
for path in sorted(pathlib.Path(sys.argv[1]).glob('*.html')):
    text = path.read_text(errors='replace')
    def meta(name):
        m = re.search(r'<meta name="%s" content="([^"]*)"' % name, text)
        return html.unescape(m[1]).strip() if m else None
    lic = re.search(r'<a [^>]*href="(https?://(?:creativecommons\.org|arxiv\.org/licenses)[^"]*)"[^>]*title="Rights to this article"', text) \
          or re.search(r'href="(https?://(?:creativecommons\.org/[^"]+|arxiv\.org/licenses/[^"]+))"', text)
    out[path.stem] = dict(title=meta('citation_title'), date=meta('citation_date'), abstract=meta('citation_abstract'),
                          licence=lic[1] if lic else None)
json.dump(out, open(sys.argv[2], 'w'), indent=1, ensure_ascii=False)
for k, v in out.items():
    print(k, '|', v['date'], '|', (v['title'] or '')[:90], '|', len(v['abstract'] or ''), '|', v['licence'])
