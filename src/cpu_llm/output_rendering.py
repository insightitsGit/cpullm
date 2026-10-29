"""Presentation directives and lossless layout of already judged responses."""
from __future__ import annotations

import html
import re
from functools import lru_cache

_FORMAT = r'(?P<format>(?:a |an )?(?:(?:markdown|html) )?(?:table|report|numbered list|bullet points|bullets))'
_SUFFIX = re.compile(r'\s+(?:as|using)\s+' + _FORMAT + r'\s*[.!?]*$', re.I)
_COMMAND_SUFFIX = re.compile(r'\s+in\s+' + _FORMAT + r'\s*[.!?]*$', re.I)
_DIRECTIVE = re.compile(r'(?:[.!?;]\s*|\n+)(?:please\s+)?(?:use|return (?:it|the answers)|present (?:it|the answers))\s+(?:as |in )?' + _FORMAT + r'\s*[.!?]*$', re.I)


def extract_layout(message):
    raw = message or ''
    masked = re.sub(r'```[\s\S]*?```|"[^"\n]*"|“[^”\n]*”', lambda m: ' ' * len(m[0]), raw)
    match = _DIRECTIVE.search(masked) or _SUFFIX.search(masked)
    if match is None and re.match(r'^(?:please\s+)?(?:show|present|list|compare|summari[sz]e|describe|explain|give|provide|tell)\b', masked, re.I):
        match = _COMMAND_SUFFIX.search(masked)
    if match is None:
        return dict(format=None, output_media='text/markdown', content_query=raw, source_end=len(raw), directive=None)
    if re.search(r"\b(?:not|don't|do not)(?:\s+use)?$", masked[:match.start()].rstrip(), re.I):
        return dict(format=None, output_media='text/markdown', content_query=raw, source_end=len(raw), directive=None)
    kind = match['format'].casefold()
    media = 'text/html' if re.search(r'\bhtml\b', kind) else 'text/markdown'
    kind = 'table' if 'table' in kind else 'report' if 'report' in kind else 'numbered' if 'numbered' in kind else 'bullets'
    return dict(format=kind, output_media=media, content_query=raw[:match.start()].rstrip(), source_end=match.start(),
                directive=raw[match.start():])


@lru_cache(maxsize=1)
def _template_environment():
    from jinja2 import DictLoader, Environment, StrictUndefined
    # Only application-owned templates are executable. Prompt/source text is
    # passed as values and never compiled as template code.
    templates = {
        'content.md.j2': '{{ content }}',
        'table.html.j2': '<section class="cpu-llm-response">{{ table_html }}</section>',
        'report.md.j2': '# Response report\n{% for row in rows %}\n## {{ row.request }}\n\n{{ row.response }}\n{% if row.sources %}\nSources: {{ row.sources }}\n{% endif %}{% endfor %}',
        'report.html.j2': '<section class="cpu-llm-response"><h1>Response report</h1>{% for row in rows %}<article><h2>{{ row.request }}</h2><div style="white-space:pre-wrap">{{ row.response }}</div>{% if row.sources %}<p>Sources: {{ row.sources|join(", ") }}</p>{% endif %}</article>{% endfor %}</section>',
        'bullets.html.j2': '<ul>{% for row in rows %}<li><div style="white-space:pre-wrap">{{ row.response }}</div>{% if row.sources %}<p>Sources: {{ row.sources|join(", ") }}</p>{% endif %}</li>{% endfor %}</ul>',
        'numbered.html.j2': '<ol>{% for row in rows %}<li><div style="white-space:pre-wrap">{{ row.response }}</div>{% if row.sources %}<p>Sources: {{ row.sources|join(", ") }}</p>{% endif %}</li>{% endfor %}</ol>',
    }
    return Environment(loader=DictLoader(templates), undefined=StrictUndefined,
                       autoescape=lambda name: bool(name and name.endswith('.html.j2')))


def _cell(value):
    # Keep source strings such as 0012 as strings; do not interpret their markup.
    return html.escape(str(value), quote=False).replace('|', r'\|').replace('\r\n', '\n').replace('\n', '<br>')


def render_response(result):
    """Only arrange the final claims; never select facts or complete a cell."""
    plan = result.get('response_plan') or {}
    kind = plan.get('format')
    if kind not in {'table', 'bullets', 'numbered', 'report'} or result.get('guard_decision') not in (None, 'allow'):
        return result
    if result.get('answer_status') == 'blocked' or not result.get('judgment'):
        return result
    rows = []
    tasks = result.get('task_results') or []
    entries = [(t.get('query', ''), t.get('result'), t.get('status')) for t in tasks] if tasks else [
        (result.get('resolved_query') or result.get('message') or '', result, result.get('answer_status'))]
    for query, child, status in entries:
        if child is None:
            text, proof = 'Pending; an earlier question needs attention.', []
        else:
            text = str((child.get('reply') or {}).get('text') or '')
            proof = list(child.get('answer_evidence') or []) + list(child.get('supporting_evidence') or [])
        sources = list(dict.fromkeys(str(p['document_id']) for p in proof if p.get('document_id')))
        rows.append(dict(request=query, response=text, status=status, sources=sources, evidence=proof))
    canonical = str((result.get('reply') or {}).get('text') or '')
    media = plan.get('output_media', 'text/markdown')
    environment = _template_environment()
    template_id = 'content.md.j2'
    if kind == 'table' and media == 'text/html':
        from tabulate import tabulate
        from markupsafe import Markup
        # Tabulate's html format escapes cells. Only its generated markup is
        # trusted here; the unsafehtml mode is deliberately not exposed.
        table = tabulate([[r['request'], r['response'], ', '.join(r['sources'])] for r in rows],
                         headers=['Request', 'Response', 'Sources'], tablefmt='html', disable_numparse=True)
        template_id = 'table.html.j2'
        text = environment.get_template(template_id).render(table_html=Markup(table))
    elif media == 'text/html':
        template_id = f'{kind}.html.j2'
        text = environment.get_template(template_id).render(rows=rows)
    elif kind == 'report':
        template_id = 'report.md.j2'
        display_rows = [dict(request=_cell(r['request']), response=_cell(r['response']),
                             sources=_cell(', '.join(r['sources']))) for r in rows]
        text = environment.get_template(template_id).render(rows=display_rows)
    elif kind == 'table':
        from tabulate import tabulate
        text = tabulate([[_cell(row['request']), _cell(row['response']), _cell(', '.join(row['sources']))]
                         for row in rows], headers=['Request', 'Response', 'Sources'],
                        tablefmt='github', disable_numparse=True)
    elif len(tasks) == 1 and (tasks[0].get('result') or {}).get('list'):
        text = rows[0]['response']
        if kind == 'numbered':
            count = iter(range(1, len(text.splitlines()) + 1))
            text = re.sub(r'(?m)^- ', lambda match: f'{next(count)}. ', text)
    elif tasks or (result.get('list') and kind == 'bullets'):
        text = canonical  # Existing list/aggregate producer already owns these units.
    elif result.get('list') and kind == 'numbered':
        count = iter(range(1, len(canonical.splitlines()) + 1))
        text = re.sub(r'(?m)^- ', lambda match: f'{next(count)}. ', canonical)
    else:
        prefix = '- ' if kind == 'bullets' else '1. '
        text = prefix + canonical.replace('\n', '\n   ')
    if template_id == 'content.md.j2':
        text = environment.get_template(template_id).render(content=text)
    result['rendered_response'] = dict(schema='rendered-response-v1', format=kind,
        media_type=media, template_id=template_id, renderer='jinja2',
        table_renderer='tabulate' if kind == 'table' else None,
        rows=rows, canonical_text=canonical, text=text,
        verification='layout of judged responses; no new factual claims')
    result['reply'] = dict(result.get('reply') or {}, text=text, format=kind, media_type=media)
    return result
