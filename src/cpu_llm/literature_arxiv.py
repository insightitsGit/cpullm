"""Opt-in prior-art lookup on arXiv for Deepen's novelty review.

Deepen's built-in novelty review checks only the caller's knowledge base. An operator can register this reviewer to
also search arXiv for the hypothesis terms::

    from cpu_llm.literature_arxiv import ArxivReviewer
    app.literature_reviewer = ArxivReviewer()
    app.ask("Deepen this.", deepen={"hypothesis": text, "novelty": True, "external_review": True})

Privacy: the hypothesis terms (not the documents) are sent to export.arxiv.org. Nothing is sent unless an operator
registers the reviewer and the request sets ``external_review``. A returned record is a candidate for human review,
never a finding: Deepen marks records naming two or more hypothesis terms as ``potential_prior_art``.
"""
from __future__ import annotations

import re
import time
import urllib.parse
import urllib.request
import xml.etree.ElementTree as ET

API = 'https://export.arxiv.org/api/query'
_ATOM = {'a': 'http://www.w3.org/2005/Atom'}
_MAX_BYTES = 2_000_000


def _phrase(term):
    words = re.findall(r'[A-Za-z0-9]+', term)[:6]
    return '"' + ' '.join(words) + '"' if words else None


def build_query(terms):
    """Any pair of hypothesis terms, each as a phrase: (all:"a" AND all:"b") OR ..."""
    phrases = [p for p in dict.fromkeys(_phrase(t) for t in terms) if p][:4]
    if len(phrases) < 2:
        return f'all:{phrases[0]}' if phrases else None
    pairs = [f'(all:{x} AND all:{y})' for i, x in enumerate(phrases) for y in phrases[i + 1:]]
    return ' OR '.join(pairs)


def parse_feed(data):
    """Records from an arXiv Atom feed; refuses DTDs (no entity expansion)."""
    if len(data) > _MAX_BYTES or b'<!DOCTYPE' in data[:2000].upper() or b'<!ENTITY' in data.upper():
        raise ValueError('Unexpected arXiv response.')
    root = ET.fromstring(data)
    records = []
    for entry in root.findall('a:entry', _ATOM):
        identifier = (entry.findtext('a:id', '', _ATOM) or '').strip()
        match = re.search(r'arxiv\.org/abs/([^\s?#]+?)(?:v\d+)?$', identifier)
        title = ' '.join((entry.findtext('a:title', '', _ATOM) or '').split())
        summary = ' '.join((entry.findtext('a:summary', '', _ATOM) or '').split())
        if match and title:
            records.append(dict(title=title[:500], url=f'https://arxiv.org/abs/{match[1]}', excerpt=summary[:3000] or title))
    return records


class ArxivReviewer:
    """Callable ``(query, max_results, timeout_seconds) -> [{title, url, excerpt}]`` for ``literature_reviewer``."""

    def __init__(self, *, api=API, min_interval=3.0, opener=None, clock=time.monotonic, sleep=time.sleep):
        self.api = api
        self.min_interval = min_interval        # arXiv asks for at most one request every three seconds
        self.opener = opener or urllib.request.urlopen
        self.clock, self.sleep = clock, sleep
        self._last = None

    def __call__(self, *, query, max_results=6, timeout_seconds=20):
        terms = [t.strip() for t in query.split(';') if t.strip()]
        search = build_query(terms)
        if search is None or timeout_seconds is None or timeout_seconds <= 1:
            return []
        if self._last is not None:
            wait = self.min_interval - (self.clock() - self._last)
            if wait > 0:
                self.sleep(min(wait, self.min_interval))
        url = self.api + '?' + urllib.parse.urlencode(dict(search_query=search, start=0,
                                                         max_results=max(1, min(int(max_results), 6))))
        request = urllib.request.Request(url, headers={'User-Agent': 'cpu-llm-literature-review'})
        self._last = self.clock()
        with self.opener(request, timeout=min(float(timeout_seconds), 20.0)) as response:
            data = response.read(_MAX_BYTES + 1)
        return parse_feed(data)[:6]
