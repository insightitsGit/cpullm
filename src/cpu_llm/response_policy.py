"""Bounded CPU classification of explicit response-depth instructions.

This is a presentation plan, not a factual-intent model. Counts are ceilings
for optional overview/list material; required proof premises are never truncated.
"""
from __future__ import annotations

import re

_NUMBER = r"(?:\d+|one|two|three|four|five|six|seven|eight|nine|ten|eleven|twelve)"
_NUMBERS = {word: index for index, word in enumerate(
    'zero one two three four five six seven eight nine ten eleven twelve'.split())}
_COUNT = re.compile(
    rf"\b(?:in|using|with|as|give(?: me)?|provide(?: me)?|list)\s+"
    rf"(?P<count>{_NUMBER})\s+(?P<unit>sentences?|bullets?(?: points?)?|points?|items?|words?)\b", re.I)
_BRIEF = re.compile(
    r"\b(?:briefly|concisely|in short|in brief|keep it short|be concise|"
    r"(?:a |the )?(?:short|brief|concise) (?:answer|response|summary|overview|explanation))\b", re.I)
_DETAIL = re.compile(
    r"\b(?:in detail|in depth|with more detail|at length|include more details?|add more details?|be thorough|thoroughly|comprehensively|"
    r"(?:a |the )?(?:long|longer|extended|full|detailed|comprehensive|thorough|in-depth) "
    r"(?:answer|response|summary|overview|explanation|account))\b", re.I)
_OVERVIEW = re.compile(r"^(?:please\s+)?(?:give(?: me)?|provide(?: me)?|write)\s+(?:an?\s+)?overview\s+(?:of|about)\s+", re.I)
_OVERVIEW_STYLE = re.compile(r"^(?:please\s+)?(?:give(?: me)?|provide(?: me)?|write)\s+(?:an?\s+)?(?:detailed|comprehensive|brief|short|thorough)\s+overview\s+(?:of|about)\s+", re.I)
_EXPLAIN = re.compile(r"^(?:please\s+)?explain\s+", re.I)
_STYLE_START = re.compile(r"^(?:please\s+)?(?:briefly|concisely|thoroughly|comprehensively)\s+", re.I)
_STYLE_COLON = re.compile(
    r"^(?:please\s+)?(?:briefly|concisely|thoroughly|comprehensively|in detail|in depth|in brief)\s*:\s*",
    re.I,
)
_STYLE_END = re.compile(r"[,;]?\s+(?:in detail|in depth|with more detail|at length|briefly|concisely|thoroughly|comprehensively)[.!?]*$", re.I)
_DEPTH_REQUEST = re.compile(
    r'^(?:please\s+)?(?:(?:can|could|would) you\s+)?(?:give(?: me)?|provide(?: me)?|write|i would like|i[’\x27]d like)\s+(?:an?\s+)?'
    r'(?:long|longer|extended|full|detailed|comprehensive|thorough)\s+'
    r'(?:answer|response|summary|overview|explanation|account)\s+(?:of|about|on|to)\s+(.+)$', re.I)
_EXPAND_REQUEST = re.compile(
    r'^(?:please\s+)?(?:(?:can|could|would) you\s+)?(?:expand on|elaborate on|tell me more about|give me more details about)\s+(.+)$', re.I)
_DEPTH_END = re.compile(
    r'(?:[.!?;]\s*|,\s*)(?:please\s+)?(?:'
    r'(?:give(?: me)?|provide(?: me)?|write)\s+(?:an?\s+)?(?:long|longer|extended|full|detailed|comprehensive|thorough)\s+(?:answer|response|summary|overview|explanation|account)|'
    r'include more details?|add more details?|be thorough)\s*[.!?]*$', re.I)
_LIMIT_END = re.compile(rf"[,;]?\s+(?:in|using|with|as)\s+{_NUMBER}\s+(?:sentences?|bullets?(?: points?)?|points?|items?|words?)[.!?]*$", re.I)
_LIMIT_START = re.compile(rf"^(?:please\s+)?(?:answer\s+)?(?:in|using|with|as)\s+{_NUMBER}\s+(?:sentences?|bullets?(?: points?)?|points?|items?|words?)\s*[:,]\s*", re.I)
_ITEM_REQUEST = re.compile(rf"^(?:please\s+)?(?:give(?: me)?|provide(?: me)?|list)\s+{_NUMBER}\s+(?:bullets?(?: points?)?|points?|items?)\s+(?:about|on|of)\s+", re.I)


def _number(text: str) -> int:
    return int(text) if text.isdigit() else _NUMBERS[text.casefold()]


def classify_response_request(message: str) -> dict:
    """Return a visible, versioned plan without searching or loading a model.

    Presentation directives are recognized in request positions, not in quoted
    source text or ordinary attributes such as 'short claws'/'long lifespan'.
    The latest explicit depth cue wins; explicit item/sentence counts override
    the relevant optional-material ceiling. Unknown wording keeps defaults.
    """
    from cpu_llm.output_rendering import extract_layout
    layout = extract_layout(message)
    text = ' '.join(layout['content_query'].strip().split())
    # Mask quoted titles/terms for classification, preserving their offsets.
    masked = re.sub(r'```[\s\S]*?```|"[^"\n]*"|“[^”\n]*”', lambda m: ' ' * len(m[0]), text)
    command = bool(re.match(r'^(?:please\s+)?(?:answer|explain|summari[sz]e|list|enumerate|give|provide|write|describe|tell|briefly|concisely|thoroughly|comprehensively)\b', masked, re.I))
    trailing_depth = _DEPTH_END.search(masked)
    depth_form = _DEPTH_REQUEST.fullmatch(masked)
    expansion = _EXPAND_REQUEST.fullmatch(masked)
    cues = []
    for detail, pattern in [('brief', _BRIEF), ('detailed', _DETAIL)]:
        for match in pattern.finditer(masked):
            if not (command or depth_form or match.start() == 0 or re.fullmatch(r'[.!?\s]*', masked[match.end():])):
                continue
            if (not command and re.search(r'\b(?:answer|response|summary|overview|explanation|account)\b', match[0], re.I)
                    and not depth_form and not (trailing_depth and match.start() >= trailing_depth.start())):
                continue
            if re.search(r"\b(?:not|don't|do not)\s+(?:(?:be|give|provide|write|want|need)(?: me)?\s+)?(?:an?\s+)?$", masked[:match.start()], re.I):
                continue
            cues.append((match.start(), detail, match[0]))
    if expansion:
        cues.append((0, 'detailed', expansion[0][:expansion.start(1)]))
    cues.sort()
    detail = cues[-1][1] if cues else 'standard'
    counts = [m for m in _COUNT.finditer(masked)
              if command or m.start() == 0 or re.fullmatch(r'[.!?\s]*', masked[m.end():])]
    limits = {}
    for match in counts:
        unit = match['unit'].casefold()
        unit = 'sentences' if unit.startswith('sentence') else 'words' if unit.startswith('word') else 'items'
        limits[unit] = _number(match['count'])
    sentence_budget = {'brief': 1, 'standard': 3, 'detailed': 8}[detail]
    item_budget = {'brief': 3, 'standard': 8, 'detailed': 12}[detail]
    if 'sentences' in limits:
        sentence_budget = max(1, min(20, limits['sentences']))
    if 'items' in limits:
        item_budget = max(1, min(20, limits['items']))
    if 'words' in limits:
        # An allocation estimate, never a claim that exact word counts are
        # enforced. Sources and required proof remain untrimmed.
        estimated = max(1, min(20, (limits['words'] + 24) // 25))
        if 'sentences' not in limits:
            sentence_budget = estimated
        if 'items' not in limits:
            item_budget = estimated
    query = text
    # Only strip anchored directives. Never remove ordinary subject words.
    if cues or counts:
        for _ in range(3):
            depth_end = _DEPTH_END.search(query)
            if depth_end:
                query = query[:depth_end.start()].rstrip()
            query = _LIMIT_START.sub('', query)
            query = _STYLE_COLON.sub('', query)
            query = _STYLE_START.sub('', query)
            query = _STYLE_END.sub('', query).rstrip(' ,;')
            query = _LIMIT_END.sub('', query).rstrip(' ,;')
    # Explicit attribute requests retain their factual slot rather than becoming
    # arbitrary summaries of the named subject.
    query = re.sub(r'^overview\s*:\s*(?=(?:what|who|where|why|how)\b)', '', query, flags=re.I)
    attribute = re.fullmatch(r'(?:give(?: me)? (?:a )?(?:detailed |brief )?account of|list)\s+(.+?)\s+(colou?r|shape|material)\s*[.!?]?', query, re.I)
    if attribute:
        query = f'What {attribute[2]} is {attribute[1]}?'
    depth_request = _DEPTH_REQUEST.fullmatch(query)
    expand_request = _EXPAND_REQUEST.fullmatch(query)
    if expand_request:
        depth_request = expand_request
    if depth_request:
        topic = depth_request[1]
        query = topic if re.match(r'^(?:what|who|where|when|why|how|which)\b', topic, re.I) else 'Tell me about ' + topic
    overview = bool(_OVERVIEW.match(query) or _OVERVIEW_STYLE.match(query) or _ITEM_REQUEST.match(query)
                    or depth_request and query.startswith('Tell me about '))
    if overview:
        query = _OVERVIEW_STYLE.sub('Tell me about ', query)
        query = _OVERVIEW.sub('Tell me about ', query)
        query = _ITEM_REQUEST.sub('Tell me about ', query)
    # A general explanation with explicit depth requests factual coverage;
    # questions containing a cause cue retain the causal producer.
    general_explanation = bool(cues or counts or layout['format']) and bool(_EXPLAIN.match(query)) and not re.search(
        r'\b(?:why|because|cause|causes|caused|reason|how come)\b', query, re.I)
    if general_explanation:
        query = _EXPLAIN.sub('Tell me about ', query)
        overview = True
    if (cues or counts or layout['format']) and re.match(r'^(?:please\s+)?(?:tell me about|describe)\s+', query, re.I):
        overview = True
    if not query.strip():
        query = text
    if not (cues or counts or overview) and query == text:
        # Untargeted requests can contain structured financial fields, source
        # excerpts, or other newline-sensitive content. Leave them verbatim.
        query = layout['content_query']
    bullets = 'items' in limits or bool(re.search(r'\b(?:bullet points|bullets)\b', masked, re.I))
    long_response = detail == 'detailed' or sentence_budget > 5 or item_budget > 8
    retrieval_budget = max(12, min(40, max(sentence_budget, item_budget if bullets else 0) + 4)) if long_response else 5
    output_format = layout['format'] or ('bullets' if bullets else 'prose')
    plan = dict(schema='response-plan-v1', detail=detail,
                explicit=bool(cues or counts or overview or layout['format']),
                mode='overview' if overview else 'existing_task',
                format=output_format, output_media=layout['output_media'],
                sentence_budget=sentence_budget, item_budget=item_budget,
                requested_limits=limits, content_query=query,
                retrieval_budget=retrieval_budget,
                flags=dict(long_response=long_response, expand_retrieval=long_response,
                           extended_overview=long_response and overview,
                           table=output_format == 'table', bullets=output_format == 'bullets',
                           numbered=output_format == 'numbered', report=output_format == 'report',
                           html=layout['output_media'] == 'text/html',
                           markdown=layout['output_media'] == 'text/markdown',
                           template_requested=layout['format'] is not None),
                reasons=[item[2] for item in cues] + [m[0] for m in counts] + (['overview request'] if overview else []),
                budget_scope='optional overview/list sentences; required proof is preserved',
                word_limit_enforced=False)
    from cpu_llm.flag_contract import enforce_response_flags
    enforce_response_flags(plan)
    return plan
