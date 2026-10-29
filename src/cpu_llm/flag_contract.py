"""Authoritative flag consumers and optional-agent routing constraints."""
from __future__ import annotations

from dataclasses import asdict, dataclass

SCHEMA = 'flag-routing-contract-v1'


@dataclass(frozen=True)
class FlagBinding:
    path: str
    origin: str
    consumers: tuple[str, ...]
    stage: str
    behavior: str
    example: str


_AGENTS = (
    ('deep', ('deep',), 'Deep search', 'Wider authorized search; not enabled by response length.'),
    ('creative', ('gather', 'imagine'), 'Imagine a story', 'Gather before imagination; no factual proof exemption.'),
    ('compare', ('compare',), 'Compare X and Y', 'Compare explicitly named sides.'),
    ('summarize', ('brief',), 'Summarize X', 'Produce source-backed summary units.'),
    ('explain', ('brief',), 'Why did X stop?', 'Prioritize supported causal explanation.'),
    ('list', ('brief',), 'List X facts', 'Produce verified list units.'),
    ('sources', ('brief', 'reply'), 'Cite the sources', 'Select and display source references.'),
    ('math', ('math',), 'Calculate 2 + 3', 'Independent arithmetic from prompt fields.'),
    ('finance', ('finance',), 'Check this refund', 'Check supplied finance fields.'),
    ('frame', ('frame',), 'What did John eat?', 'Resolve a source-backed event frame.'),
    ('draft', ('reply',), 'Draft a letter about X', 'Document catalog is rendered inside reply; no separate draft node.'),
    ('discover', ('discover',), 'API discover=True', 'API-only follow-up suggestions after reply; never inferred from layout.'),
)
_PRESENTATION = (
    ('long_response', ('retrieve', 'brief'), 'budget', 'Long response about X', 'Derived depth/size indicator; consumers use validated numeric budgets.'),
    ('expand_retrieval', ('retrieve',), 'budget', 'Explain X in 20 sentences', 'Must agree with long_response; use retrieval_budget, not the deep-search agent.'),
    ('extended_overview', ('brief',), 'budget', 'Elaborate on X', 'Long response plus overview mode; direct factual slots are unchanged.'),
    ('table', ('render_response',), 'post_graph', 'as a table', 'Tabulate plus built-in Jinja layout after judgment.'),
    ('bullets', ('brief', 'render_response'), 'presentation', 'as bullet points', 'Overview uses list producer; a direct fact remains a fact.'),
    ('numbered', ('brief', 'render_response'), 'presentation', 'as a numbered list', 'Use verified item boundaries and numbered layout.'),
    ('report', ('render_response',), 'post_graph', 'as a report', 'Built-in task-response report; distinct from legacy draft report.'),
    ('html', ('render_response',), 'post_graph', 'as an HTML report', 'Escaped HTML output; does not choose a factual agent.'),
    ('markdown', ('render_response',), 'post_graph', 'as a Markdown table', 'Markdown representation; default does not force a template.'),
    ('template_requested', ('render_response',), 'post_graph', 'Please use a table', 'Explicit layout indicator; validated against format/media.'),
)
FLAG_BINDINGS = tuple(
    FlagBinding('state.' + name, 'API-only' if name == 'discover' else
                'prompt or explicit API override' if name in {'deep', 'creative', 'math', 'finance'} else
                'recognized prompt / internal interpretation', nodes, 'graph', behavior, example)
    for name, nodes, example, behavior in _AGENTS
) + tuple(
    FlagBinding('response_plan.flags.' + name, 'explicit prompt presentation or derived default', nodes, stage, behavior, example)
    for name, nodes, stage, example, behavior in _PRESENTATION
) + tuple(
    FlagBinding(f'prompt_intent.channels.{name}.active', 'recognized request form / channel evidence',
                ('retrieve', name), 'channel', 'All six channel nodes evaluate; active is a signal, not a graph skip or proof.', example)
    for name, example in [('dense', 'Any content query'), ('relational', 'What does X have?'),
                          ('disentangled', 'How do X and Y differ?'), ('hyperbolic', 'What type is X?'),
                          ('identity', 'Who is X?'), ('causal', 'Why did X stop?')]
)
OPTIONAL_ORDER = ('deep', 'gather', 'compare', 'brief', 'math', 'finance', 'frame')
_AFTER = {'shine': -1, 'deep': 0, 'imagine': 1, 'compare': 2, 'brief': 3, 'math': 4, 'finance': 5, 'frame': 6}
_INDEPENDENT = frozenset({'math', 'finance'})


def mapping_records():
    return [asdict(binding) for binding in FLAG_BINDINGS]


def delivery_held(state):
    return bool(state.get('delivery_blocked') or state.get('shine_enforced') or state.get('shine_ok') is False)


def node_requested(node, state):
    return any(state.get(binding.path.removeprefix('state.')) is True
               for binding in FLAG_BINDINGS if binding.stage == 'graph' and node in binding.consumers)


def next_optional(state, after):
    if state.get('guard_decision') not in (None, 'allow'):
        return 'reply'
    for node in OPTIONAL_ORDER[_AFTER[after] + 1:]:
        if node_requested(node, state) and (node in _INDEPENDENT or not delivery_held(state)):
            return node
    return 'model01'


def enforce_node_request(node, state):
    optional = set(OPTIONAL_ORDER) | {'imagine', 'discover'}
    if node not in optional:
        return
    if state.get('guard_decision') not in (None, 'allow') or not node_requested(node, state):
        raise ValueError(f'Unrequested or guard-blocked optional node: {node}')
    if node not in _INDEPENDENT | {'discover'} and delivery_held(state):
        raise ValueError(f'Delivery-held node cannot consume retrieved claims: {node}')


def validate_graph_consumers(nodes):
    external = {'render_response'}
    expected = {node for binding in FLAG_BINDINGS for node in binding.consumers} - external
    if missing := expected - set(nodes):
        raise ValueError('Flag consumers missing from graph: ' + ', '.join(sorted(missing)))


def enforce_response_flags(plan):
    """Reject a drifted internal flag/format/media contract before using it."""
    if plan.get('schema') != 'response-plan-v1':
        return  # Legacy/internal producers may have no presentation contract.
    flags = plan.get('flags') or {}
    expected = {row[0] for row in _PRESENTATION}
    if set(flags) != expected or any(type(value) is not bool for value in flags.values()):
        raise ValueError('Unmapped or missing response flags')
    kind, media = plan['format'], plan['output_media']
    if kind not in {'prose', 'table', 'bullets', 'numbered', 'report'} or media not in {'text/html', 'text/markdown'}:
        raise ValueError('Unsupported format/media contract')
    for name in ('table', 'bullets', 'numbered', 'report'):
        if flags[name] != (kind == name):
            raise ValueError(f'Flag disagrees with response format: {name}')
    if flags['html'] != (media == 'text/html') or flags['markdown'] != (media == 'text/markdown'):
        raise ValueError('Media flags disagree with output_media')
    if flags['template_requested'] and kind == 'prose' or flags['html'] and not flags['template_requested']:
        raise ValueError('Explicit template flag disagrees with layout/media')
    if flags['expand_retrieval'] != flags['long_response']:
        raise ValueError('Retrieval expansion disagrees with response length')
    if flags['extended_overview'] != (flags['long_response'] and plan['mode'] == 'overview'):
        raise ValueError('Overview flag disagrees with request mode')
    if flags['expand_retrieval'] and plan['retrieval_budget'] < 12:
        raise ValueError('Long-response retrieval budget was not connected')
    if not flags['expand_retrieval'] and plan['retrieval_budget'] != 5:
        raise ValueError('Unexpected expanded retrieval without its flag')
    for key, ceiling in [('sentence_budget', 20), ('item_budget', 20), ('retrieval_budget', 40)]:
        if type(plan[key]) is not int or not 1 <= plan[key] <= ceiling:
            raise ValueError('Invalid bounded budget: ' + key)


def routing_snapshot(turn):
    return dict(schema=SCHEMA, requested_flags=dict(turn.get('routing_flags') or {}),
                executed_nodes=list(turn.get('executed_nodes') or []),
                observed=bool(turn.get('executed_nodes')), post_stages=[])
