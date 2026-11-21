"""Natural-language routes to the Frontier and Deepen nodes.

The explicit forms (``Frontier: <topic>.``, ``Deepen: <hypothesis>.``) always route. The natural forms below route
only when no existing specialist (Nammade, CrossDomain, Invention, Research) claims the prompt, so every prompt that
routed before keeps its route. A polite request shell ("Could you please ...") is removed first, the same way the
prompt-ingestion stage removes inquiry shells.

Frontier, natural forms (topic captured):
- "Explore the frontier / open questions / unknowns / hypothesis space of X"
- "What unexplored (untested, unknown, hidden, overlooked) connections (possibilities, mechanisms, ...) exist around X?"
- "Find / list / suggest / surface untested (non-obvious, frontier, ...) hypotheses (ideas, links, ...) about X"
- "What don't we know about X?" / "What does the literature not know about X?"
- "What might be true about X that no source (paper, study) states?"
- "Frontier hypotheses (ideas, search) about X"

Deepen, natural forms (the rest must parse as a hypothesis in a Frontier form):
- "Check / test / examine / evaluate / assess / probe / vet / dig into this hypothesis: <hypothesis>"
- "Is it true (plausible, likely) that <hypothesis>?" / "How well supported is the hypothesis that <hypothesis>?"
- Session follow-up after a Frontier answer: "Deepen idea 3", "Check hypothesis #2", "Examine number 5".
"""
from __future__ import annotations

import re

_SHELL = re.compile(r'^(?:please\s+)?(?:(?:can|could|would|will)\s+you\s+(?:please\s+)?)?(?:help me\s+)?', re.I)
_OBJECTS = (r'(?:possibilities|connections|links|mechanisms|explanations|relationships|hypotheses|hypothesis|ideas|'
            r'factors|research directions|directions|pathways|interactions)')
_ADJECTIVES = r'(?:unknown|unexplored|untested|undiscovered|hidden|overlooked|non[- ]obvious|novel|frontier)'
_PREPOSITIONS = r'(?:about|for|in|on|around|behind|across|between|regarding|of|concerning)'
_FRONTIER_FORMS = tuple(re.compile(form, re.I) for form in (
    r'(?:explore|map|survey|chart)\s+(?:the\s+)?(?:frontiers?|unknowns?|open questions|unexplored (?:territory|space|'
    r'connections)|hypothesis space|space of (?:possible\s+)?(?:hypotheses|explanations))\s+'
    + _PREPOSITIONS + r'\s+(?P<topic>.+)',
    r'(?:what|which)\s+(?:are\s+)?(?:the\s+)?(?:possible\s+|plausible\s+|candidate\s+)?' + _ADJECTIVES + r'\s+'
    + _OBJECTS + r'\s+(?:are there\s+|exist\s+|might exist\s+|could exist\s+)?' + _PREPOSITIONS + r'\s+(?P<topic>.+)',
    r'(?:find|list|show(?: me)?|give me|suggest|propose|surface|generate|uncover)\s+(?:some\s+|many\s+|several\s+|'
    r'the\s+|\d+\s+)?(?:possible\s+|plausible\s+|candidate\s+)?' + _ADJECTIVES + r'\s+' + _OBJECTS + r'\s+'
    + _PREPOSITIONS + r'\s+(?P<topic>.+)',
    r'what\s+(?:do\s+we|does\s+(?:the\s+)?(?:literature|knowledge base|research|field))\s+(?:not|n[o’\']?t)\s+'
    r'(?:yet\s+)?know\s+(?:yet\s+)?about\s+(?P<topic>.+)',
    r'what\s+(?:don[’\']t|do not)\s+we\s+(?:yet\s+)?know\s+(?:yet\s+)?about\s+(?P<topic>.+)',
    r'what\s+(?:might|could)\s+(?:be\s+)?(?:true|possible|going on)\s+(?:about|in|with)\s+(?P<topic>.+?)\s+that\s+no\s+'
    r'(?:single\s+)?(?:source|paper|study|document|article)\s+(?:says|states|shows|reports)',
    r'frontier\s+(?:hypotheses|ideas|possibilities|research|search|analysis)\s+' + _PREPOSITIONS + r'\s+(?P<topic>.+)',
))
_DEEPEN_FORMS = tuple(re.compile(form, re.I) for form in (
    r'(?:check|test|examine|evaluate|assess|scrutini[sz]e|stress[- ]test|deepen|dig into|probe|vet)\s+'
    r'(?:this|the|my|a|that|our)?\s*(?:hypothesis|idea|claim|conjecture)\s*(?::|-|that\b)?\s*(?P<hypothesis>.+)',
    r'(?:is it (?:true|plausible|likely)|how (?:well[- ]supported|strong|plausible|good) is (?:the |this )?'
    r'(?:idea|hypothesis|claim)?)\s*(?:that\s+)?(?P<hypothesis>.+)',
))
_FOLLOW_UP = re.compile(
    r'(?:deepen|check|test|examine|evaluate|assess|dig into|probe|vet)\s+(?:the\s+)?(?:hypothesis|idea|entry|item|'
    r'number|no\.?|#)?\s*#?\s*(?P<number>\d{1,2})', re.I)


def _strip(message):
    """Remove a polite request shell, then the prompt-ingestion inquiry shell ("I'd like to know ...")."""
    from cpu_llm.prompt_ingestion import _SHELL as INQUIRY_SHELL

    text = _SHELL.sub('', (message or '').strip(), count=1).strip()
    inquiry = INQUIRY_SHELL.match(text)
    if inquiry:
        text = text[inquiry.end():]
    return text.strip().rstrip('?.!').strip()


def _claimed_by_existing_route(message):
    """True when Nammade, CrossDomain, Invention or Research already claims the prompt."""
    from cpu_llm.cross_domain import cross_domain_seed
    from cpu_llm.invention import invention_seed
    from cpu_llm.nammade import nammade_seed
    from cpu_llm.nammade.execute import research_scan_seed

    return any(seed(message) is not None for seed in (nammade_seed, cross_domain_seed, invention_seed,
                                                      research_scan_seed))


def natural_frontier_topic(message):
    """The topic of a natural Frontier request, or None."""
    text = _strip(message)
    for form in _FRONTIER_FORMS:
        match = form.fullmatch(text)
        if match:
            topic = match['topic'].strip().rstrip('?.!').strip()
            if topic and not _claimed_by_existing_route(message):
                return topic
    return None


def natural_deepen_target(message):
    """The hypothesis text of a natural Deepen request, a ``('follow_up', n)`` pair, or None."""
    from cpu_llm.deepen import parse_hypothesis

    text = _strip(message)
    follow_up = _FOLLOW_UP.fullmatch(text)
    if follow_up and not _claimed_by_existing_route(message):
        return ('follow_up', int(follow_up['number']))
    for form in _DEEPEN_FORMS:
        match = form.fullmatch(text)
        if not match:
            continue
        hypothesis = match['hypothesis'].strip()
        try:
            parse_hypothesis(hypothesis)
        except ValueError:
            continue
        if not _claimed_by_existing_route(message):
            return hypothesis
    return None


def _sessions(app):
    from cpu_llm.request_planner import RequestSessions

    sessions = getattr(app, 'frontier_sessions', None)
    return sessions if sessions is not None else app.__dict__.setdefault('frontier_sessions', RequestSessions())


def remember_frontier(app, key, result):
    """Keep the hypotheses of a Frontier answer so "Deepen idea N" can select one in the same session."""
    hypotheses = (result.get('frontier') or {}).get('hypotheses') or []
    if key is not None and hypotheses:
        _sessions(app).save(key, dict(hypotheses=hypotheses))


def recall_frontier(app, key, number):
    """Return (hypothesis, None) or (None, reason) for a numbered follow-up."""
    if key is None:
        return None, 'Pass a session_id with the Frontier request to refer to its hypotheses by number.'
    sessions = _sessions(app)
    state = sessions.pop(key)
    if state is None:
        return None, 'There is no Frontier answer in this session. Run "Frontier: <topic>." first.'
    sessions.save(key, state)
    hypotheses = state['hypotheses']
    if not 1 <= number <= len(hypotheses):
        return None, f'The last Frontier answer has {len(hypotheses)} hypotheses; choose a number from 1 to {len(hypotheses)}.'
    return hypotheses[number - 1], None
